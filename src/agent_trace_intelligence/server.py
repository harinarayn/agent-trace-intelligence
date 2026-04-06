import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from dotenv import load_dotenv

from .tools.judge_trace import judge_trace
from .tools.trace_breakdown import trace_breakdown
from .tools.efficiency_score import efficiency_score

load_dotenv()

server = Server("agent-trace-intelligence")

# --- Tool definitions (what the MCP client sees) ---


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="judge_trace",
            description="Diagnoses an agent trace — identifies root causes of failure, scores performance across four dimensions, and suggests a concrete fix. Returns verdict, grade, and plain-English explanation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {
                        "type": "string",
                        "description": "Agent trace as a JSON string conforming to AgentTrace schema",
                    },
                    "goal": {
                        "type": "string",
                        "description": "Optional: override the goal stated in the trace",
                    },
                },
                "required": ["trace"],
            },
        ),
        types.Tool(
            name="trace_breakdown",
            description="Step-by-step scoring of every agent decision. Flags issues like redundant tool calls, reasoning gaps, and goal drift.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {
                        "type": "string",
                        "description": "Agent trace as a JSON string conforming to AgentTrace schema",
                    }
                },
                "required": ["trace"],
            },
        ),
        types.Tool(
            name="efficiency_score",
            description="Deterministic efficiency analysis of token usage, tool redundancy, and latency. No API key required — runs instantly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {
                        "type": "string",
                        "description": "Agent trace as a JSON string conforming to AgentTrace schema",
                    }
                },
                "required": ["trace"],
            },
        ),
    ]


# --- Tool dispatch ---


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "judge_trace":
        result = await judge_trace(
            trace_json=arguments["trace"], goal=arguments.get("goal")
        )
    elif name == "trace_breakdown":
        result = await trace_breakdown(trace_json=arguments["trace"])
    elif name == "efficiency_score":
        result = await efficiency_score(trace_json=arguments["trace"])
    else:
        result = json.dumps(
            {
                "error": True,
                "error_code": "UNKNOWN_TOOL",
                "error_message": f"Unknown tool: {name}",
            }
        )

    return [types.TextContent(type="text", text=result)]


# --- Entrypoint ---


async def _main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Sync entrypoint required by pyproject.toml scripts."""
    asyncio.run(_main())
