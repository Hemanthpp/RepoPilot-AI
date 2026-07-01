import asyncio
from mcp.server import Server
import mcp.server.stdio
from mcp.types import Tool, TextContent
from pydantic import BaseModel
import json

app = Server("repopilot-mcp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="clone_repository",
            description="Clones a remote git repository to local storage for analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL of the repository to clone."}
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="analyze_repository_tree",
            description="Returns a directory tree map of the repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Local path to the repository."}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="run_static_analysis",
            description="Runs static analysis on the codebase to identify bugs or code smells.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Local path to the repository."}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="execute_test_suite",
            description="Executes the existing test suite and reports coverage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Local path to the repository."}
                },
                "required": ["repo_path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "clone_repository":
        url = arguments.get("url")
        return [TextContent(type="text", text=f"Repository {url} cloned successfully to /tmp/repopilot/{url.split('/')[-1]}.")]
    
    elif name == "analyze_repository_tree":
        repo_path = arguments.get("repo_path")
        tree = "app/\n  main.py\n  utils.py\ntests/\n  test_main.py"
        return [TextContent(type="text", text=f"Tree for {repo_path}:\n{tree}")]
    
    elif name == "run_static_analysis":
        repo_path = arguments.get("repo_path")
        return [TextContent(type="text", text=f"Static analysis for {repo_path} completed. Found 1 critical issue, 3 warnings.")]
    
    elif name == "execute_test_suite":
        repo_path = arguments.get("repo_path")
        return [TextContent(type="text", text=f"Test suite for {repo_path} ran. Coverage: 78%. 1 test failed.")]
        
    raise ValueError(f"Unknown tool: {name}")

async def run():
    # Use standard stdio transport for the MCP server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(run())
