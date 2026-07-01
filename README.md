# 🚀 RepoPilot AI

**Autonomous multi-agent repository analysis & engineering assistant** powered by Google ADK 2.0.

Welcome to the root repository for RepoPilot AI! This project takes a GitHub or GitLab repository URL and delivers a comprehensive engineering report — architecture analysis, security scanning, code review, test generation, and documentation — all orchestrated by an intelligent multi-agent workflow with built-in security guardrails.

## 📁 Repository Structure

- **[`repopilot-ai/`](repopilot-ai/)** - The main application code and agent logic. **Start here** for the primary project files, instructions, and tests.
- **[`GETTING_STARTED.md`](GETTING_STARTED.md)** - Guide on how to get started with the project.
- **[`agent_builder_playbook.md`](agent_builder_playbook.md)** - Documentation and playbook for building agents.

## 🚀 Quick Start

To jump right into running the agent, see the full instructions in the [main README](repopilot-ai/README.md).

```bash
cd repopilot-ai
cp .env.example .env   # add your GOOGLE_API_KEY
make install
make playground        # opens UI at http://localhost:18081
```
*(Windows users: Use `uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents` instead of `make playground`)*

---
*Built for the Google ADK Agents Capstone.*
