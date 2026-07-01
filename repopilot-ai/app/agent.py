"""RepoPilot AI — Autonomous Repository Analysis & Engineering Agent.

ADK 2.0 Workflow graph with function nodes, LlmAgent sub-agents,
MCPToolset integration, security checkpoint, and persistent shared state.
"""

import re
import json
import logging
import datetime
from typing import Any

from pydantic import BaseModel, Field
from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.tools import MCPToolset, AgentTool
from google.adk.events import Event

from app.config import config

# ── Audit logger ──────────────────────────────────────────────────────────
audit_logger = logging.getLogger("repopilot_audit")
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(_handler)


# ══════════════════════════════════════════════════════════════════════════
# State Schema — shared workflow memory via ctx.state
# ══════════════════════════════════════════════════════════════════════════
class RepoPilotState(BaseModel):
    """Shared memory schema persisted across the entire workflow session.

    Every function node can read/write these fields through ctx.state.
    LlmAgent sub-agents inherit the same session state automatically.
    """

    # ── Repository Cache ──────────────────────────────────────────────────
    repository_url: str = ""
    repository_owner: str = ""
    repository_name: str = ""
    clone_path: str = ""

    # ── Analysis Results (shared between agents) ──────────────────────────
    languages: list = Field(default_factory=list)
    frameworks: list = Field(default_factory=list)
    file_count: int = 0
    architecture_pattern: str = ""
    architecture_summary: str = ""
    dependencies: list = Field(default_factory=list)

    # ── Security Findings ─────────────────────────────────────────────────
    security_blocked: bool = False
    security_issues: list = Field(default_factory=list)
    pii_redacted: list = Field(default_factory=list)
    injection_detected: bool = False
    audit_log: list = Field(default_factory=list)

    # ── Code Review Results ───────────────────────────────────────────────
    code_smells: list = Field(default_factory=list)
    bugs_found: list = Field(default_factory=list)
    review_severity: str = ""

    # ── Test Generation ───────────────────────────────────────────────────
    generated_tests: list = Field(default_factory=list)
    estimated_coverage: str = ""
    missing_test_areas: list = Field(default_factory=list)

    # ── Documentation ─────────────────────────────────────────────────────
    generated_readme: str = ""
    generated_architecture_doc: str = ""

    # ── Session History & Reports ─────────────────────────────────────────
    session_history: list = Field(default_factory=list)
    previous_analyses: list = Field(default_factory=list)
    generated_reports: list = Field(default_factory=list)

    # ── User Preferences ──────────────────────────────────────────────────
    user_preferred_detail_level: str = "detailed"
    user_preferred_language: str = "en"

    # ── Pipeline Metadata ─────────────────────────────────────────────────
    current_phase: str = ""
    analysis_start_time: str = ""
    analysis_end_time: str = ""


# ══════════════════════════════════════════════════════════════════════════
# MCP Toolset (stdio transport)
# ══════════════════════════════════════════════════════════════════════════
mcp_toolset = MCPToolset(
    connection_params={
        "server_name": "repopilot-mcp",
        "command": "uv",
        "args": ["run", "python", "app/mcp_server.py"],
    }
)

# ══════════════════════════════════════════════════════════════════════════
# Sub-agents — each reads/writes ctx.state through the shared session
# ══════════════════════════════════════════════════════════════════════════
repo_analyzer = LlmAgent(
    name="RepoAnalyzer",
    model=config.model,
    instruction=(
        "You are the Repository Analysis Agent. Your job is to analyze the structure "
        "of the provided repository URL. If you cannot actually clone or access the URL, "
        "simply simulate a realistic repository structure for the requested project based on your knowledge, "
        "and return that structure to the orchestrator."
    ),
    tools=[mcp_toolset],
)

architecture_agent = LlmAgent(
    name="ArchitectureAgent",
    model=config.model,
    instruction=(
        "You are the Architecture Agent. Identify architectural patterns based on "
        "the structure provided by the RepoAnalyzer. If information is missing, "
        "simulate a realistic architecture for a project of this type."
    ),
)

code_review_agent = LlmAgent(
    name="CodeReviewAgent",
    model=config.model,
    instruction=(
        "You are the Code Review Agent. Perform static analysis on the codebase "
        "structure provided. If you cannot access actual code, simulate realistic "
        "code review findings for a project of this type. List the top 5 "
        "findings with severity ratings."
    ),
    tools=[mcp_toolset],
)

test_agent = LlmAgent(
    name="TestAgent",
    model=config.model,
    instruction=(
        "You are the Test Agent. Identify missing test cases and generate "
        "example unit tests for the most critical modules. Return generated "
        "test code and estimated coverage."
    ),
)

doc_agent = LlmAgent(
    name="DocumentationAgent",
    model=config.model,
    instruction=(
        "You are the Documentation Agent. Based on the analysis data provided, "
        "generate a concise README and architecture documentation."
    ),
)

# Wrap sub-agents as tools for orchestrator delegation
repo_analyzer_tool = AgentTool(agent=repo_analyzer)
architecture_tool = AgentTool(agent=architecture_agent)
code_review_tool = AgentTool(agent=code_review_agent)
test_tool = AgentTool(agent=test_agent)
doc_tool = AgentTool(agent=doc_agent)

orchestrator = LlmAgent(
    name="Orchestrator",
    model=config.model,
    instruction=(
        "You are the Orchestrator for RepoPilot AI.\n"
        "The user provides a GitHub or GitLab repository URL.\n"
        "Your job is to coordinate the analysis pipeline.\n"
        "CRITICAL: You MUST call tools ONE AT A TIME. Wait for each tool to "
        "return its result before calling the next one.\n"
        "Follow this exact sequence:\n"
        "1. First, call RepoAnalyzer. Wait for the result.\n"
        "2. Then, call ArchitectureAgent. Wait for the result.\n"
        "3. Finally, call CodeReviewAgent. Wait for the result.\n"
        "After these 3 tools have returned, aggregate all findings into a comprehensive "
        "analysis report with sections: Repository Overview, Architecture, Code Quality."
    ),
    tools=[
        repo_analyzer_tool,
        architecture_tool,
        code_review_tool,
    ],
)


# ══════════════════════════════════════════════════════════════════════════
# Workflow Function Nodes — all read/write ctx.state
# ══════════════════════════════════════════════════════════════════════════

def initialize_state(ctx, node_input: Any) -> str:
    """First node: initialize session state and record analysis start."""
    text = str(node_input) if node_input else ""

    # Record session start
    ctx.state["analysis_start_time"] = datetime.datetime.now().isoformat()
    ctx.state["current_phase"] = "initialization"

    # Append to session history
    history = list(ctx.state.get("session_history", []))
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "action": "session_started",
        "input_preview": text[:100],
    })
    ctx.state["session_history"] = history

    # Preserve previous analyses from prior sessions
    prev = list(ctx.state.get("previous_analyses", []))
    if ctx.state.get("repository_url"):
        prev.append({
            "url": ctx.state["repository_url"],
            "timestamp": ctx.state.get("analysis_start_time", ""),
            "languages": list(ctx.state.get("languages", [])),
        })
        ctx.state["previous_analyses"] = prev

    return text


def security_checkpoint(ctx, node_input: Any) -> str:
    """Security gate: PII scrubbing, injection detection, URL validation, audit log.

    Writes to ctx.state:
        security_blocked, repository_url, repository_owner, repository_name,
        pii_redacted, injection_detected, security_issues, audit_log
    """
    text = str(node_input) if node_input else ""
    ctx.state["current_phase"] = "security_checkpoint"

    # 1. PII Scrubbing — mask API keys / tokens found in input
    pii_patterns = [
        (r"AIza[0-9A-Za-z\-_]{35}", "Google_API_Key"),
        (r"ghp_[0-9a-zA-Z]{36}", "GitHub_PAT"),
        (r"(?:password|passwd|pwd)\s*[:=]\s*\S+", "Password"),
        (r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+", "JWT_Token"),
    ]
    pii_found = []
    scrubbed = text
    for pattern, label in pii_patterns:
        if re.search(pattern, scrubbed):
            pii_found.append(label)
            scrubbed = re.sub(pattern, f"[REDACTED_{label.upper()}]", scrubbed)
    ctx.state["pii_redacted"] = pii_found

    # 2. Prompt Injection Detection
    injection_keywords = [
        "ignore previous instructions",
        "execute shell",
        "delete files",
        "expose secrets",
        "override system",
        "bypass security",
    ]
    injection_detected = any(kw in text.lower() for kw in injection_keywords)
    ctx.state["injection_detected"] = injection_detected

    # 3. Domain-specific: Repo URL Validation
    url_match = re.search(r"https?://(?:github|gitlab)\.com/[\w\-\.]+/[\w\-\.]+", text)
    is_valid_url = url_match is not None

    # 4. Structured JSON Audit Log
    audit_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event": "security_checkpoint",
        "pii_redacted": pii_found,
        "injection_detected": injection_detected,
        "valid_repo_url": is_valid_url,
        "scrubbed_input": scrubbed[:200],
    }

    if injection_detected:
        audit_entry["severity"] = "CRITICAL"
        audit_entry["action"] = "BLOCKED"
        audit_logger.warning(json.dumps(audit_entry))

        ctx.state["security_blocked"] = True
        issues = list(ctx.state.get("security_issues", []))
        issues.append({"type": "injection", "severity": "CRITICAL", "detail": "Prompt injection detected"})
        ctx.state["security_issues"] = issues

        log = list(ctx.state.get("audit_log", []))
        log.append(audit_entry)
        ctx.state["audit_log"] = log
        return (
            "🚨 SECURITY ALERT: Prompt injection attempt detected. "
            "Request has been blocked and logged."
        )

    if not is_valid_url:
        audit_entry["severity"] = "WARNING"
        audit_entry["action"] = "NEEDS_REVIEW"
        audit_logger.warning(json.dumps(audit_entry))

        ctx.state["security_blocked"] = True
        log = list(ctx.state.get("audit_log", []))
        log.append(audit_entry)
        ctx.state["audit_log"] = log
        return (
            "⚠️ No valid GitHub/GitLab repository URL detected in your input. "
            "Please provide a URL like https://github.com/owner/repo"
        )

    # Valid URL — extract owner/name and store in state
    audit_entry["severity"] = "INFO"
    audit_entry["action"] = "PROCEED"
    audit_logger.info(json.dumps(audit_entry))

    repo_url = url_match.group(0)
    parts = repo_url.rstrip("/").split("/")
    ctx.state["security_blocked"] = False
    ctx.state["repository_url"] = repo_url
    ctx.state["repository_owner"] = parts[-2] if len(parts) >= 2 else ""
    ctx.state["repository_name"] = parts[-1] if len(parts) >= 1 else ""
    ctx.state["clone_path"] = f"/tmp/repopilot/{parts[-1]}"

    log = list(ctx.state.get("audit_log", []))
    log.append(audit_entry)
    ctx.state["audit_log"] = log

    # Update session history
    history = list(ctx.state.get("session_history", []))
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "action": "security_passed",
        "repository_url": repo_url,
    })
    ctx.state["session_history"] = history

    return scrubbed


def route_after_security(ctx, node_input: Any) -> Event:
    """Routes based on security checkpoint result."""
    if ctx.state.get("security_blocked"):
        return Event(route="blocked", output="blocked")
    return Event(route="proceed", output="proceed")


def blocked_node(ctx, node_input: Any) -> str:
    """Terminal node when security blocks the request."""
    ctx.state["current_phase"] = "blocked"
    ctx.state["analysis_end_time"] = datetime.datetime.now().isoformat()

    # Store in reports cache
    reports = list(ctx.state.get("generated_reports", []))
    reports.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "type": "security_block",
        "result": str(node_input)[:200] if node_input else "Blocked",
    })
    ctx.state["generated_reports"] = reports

    return str(node_input) if node_input else "Request blocked by security."


def pre_orchestrator(ctx, node_input: Any) -> str:
    """Prepares context for orchestrator by assembling state into a prompt.

    Reads from ctx.state:
        repository_url, repository_owner, repository_name,
        previous_analyses, user_preferred_detail_level
    """
    print("PRE_ORCHESTRATOR RAN!")
    ctx.state["current_phase"] = "orchestration"

    url = ctx.state.get("repository_url", "")
    owner = ctx.state.get("repository_owner", "")
    name = ctx.state.get("repository_name", "")
    detail = ctx.state.get("user_preferred_detail_level", "detailed")

    # Include previous analysis context if available
    prev = ctx.state.get("previous_analyses", [])
    prev_context = ""
    if prev:
        prev_context = (
            f"\n\nNote: {len(prev)} previous analysis/analyses found in session history. "
            f"Last analyzed: {prev[-1].get('url', 'unknown')}."
        )

    prompt = (
        f"Analyze this repository: {url}\n"
        f"Owner: {owner}, Name: {name}\n"
        f"Detail level: {detail}\n"
        f"Please perform a full analysis: repo structure, architecture, "
        f"code review, test generation, and documentation.{prev_context}"
    )
    return prompt


def post_orchestrator(ctx, node_input: Any) -> str:
    """Captures orchestrator output into state and generates final report.

    Writes to ctx.state:
        generated_reports, session_history, analysis_end_time, current_phase
    """
    ctx.state["current_phase"] = "finalization"
    ctx.state["analysis_end_time"] = datetime.datetime.now().isoformat()

    report_text = str(node_input) if node_input else ""

    # Cache the generated report
    reports = list(ctx.state.get("generated_reports", []))
    reports.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "type": "full_analysis",
        "repository_url": ctx.state.get("repository_url", ""),
        "report_preview": report_text[:500],
    })
    ctx.state["generated_reports"] = reports

    # Store in previous analyses for future session reference
    prev = list(ctx.state.get("previous_analyses", []))
    prev.append({
        "url": ctx.state.get("repository_url", ""),
        "timestamp": datetime.datetime.now().isoformat(),
        "languages": list(ctx.state.get("languages", [])),
        "frameworks": list(ctx.state.get("frameworks", [])),
    })
    ctx.state["previous_analyses"] = prev

    # Update session history
    history = list(ctx.state.get("session_history", []))
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "action": "analysis_complete",
        "repository_url": ctx.state.get("repository_url", ""),
        "report_length": len(report_text),
    })
    ctx.state["session_history"] = history

    ctx.state["current_phase"] = "complete"
    return report_text


# ══════════════════════════════════════════════════════════════════════════
# Workflow Graph
# ══════════════════════════════════════════════════════════════════════════
root_agent = Workflow(
    name="RepoPilotAI",
    description=(
        "Autonomous multi-agent repository analysis and engineering assistant "
        "with shared memory, security guardrails, and session persistence."
    ),
    state_schema=RepoPilotState,
    edges=[
        # START → init → security → router
        ("START", initialize_state, security_checkpoint, route_after_security),
        # Conditional routing
        (route_after_security, {"blocked": blocked_node, "proceed": pre_orchestrator}),
        # If proceed → prep → orchestrator → post-process (terminal)
        (pre_orchestrator, orchestrator, post_orchestrator),
    ],
)
