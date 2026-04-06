"""
Tests for MCP server import and tool registration.
No API key needed, runs in CI.
"""
import asyncio
import json
import pytest


class TestServerImport:
    def test_server_imports_without_error(self):
        from agent_trace_intelligence import server as server_module
        assert server_module is not None

    def test_server_object_exists(self):
        from agent_trace_intelligence.server import server
        assert server is not None

    def test_server_has_correct_name(self):
        from agent_trace_intelligence.server import server
        assert server.name == "agent-trace-intelligence"

    def test_main_function_exists(self):
        from agent_trace_intelligence.server import main
        assert callable(main)


class TestToolRegistration:
    def test_list_tools_handler_exists(self):
        """Server must have list_tools handler registered."""
        from agent_trace_intelligence.server import server
        # The MCP Server registers handlers internally
        # We verify by checking the server object has the attribute
        assert hasattr(server, "list_tools")

    def test_call_tool_handler_exists(self):
        """Server must have call_tool handler registered."""
        from agent_trace_intelligence.server import server
        assert hasattr(server, "call_tool")

    def test_list_tools_returns_three_tools(self):
        """Exactly 3 tools must be registered."""
        from agent_trace_intelligence.server import list_tools

        async def _check():
            tools = await list_tools()
            return tools

        tools = asyncio.get_event_loop().run_until_complete(_check())
        assert len(tools) == 3, f"Expected 3 tools, got {len(tools)}: {[t.name for t in tools]}"

    def test_tool_names_correct(self):
        """All three required tool names must be present."""
        from agent_trace_intelligence.server import list_tools

        async def _check():
            return await list_tools()

        tools = asyncio.get_event_loop().run_until_complete(_check())
        tool_names = {t.name for t in tools}
        assert "judge_trace" in tool_names
        assert "trace_breakdown" in tool_names
        assert "efficiency_score" in tool_names

    def test_each_tool_has_required_schema_fields(self):
        """Each tool must have name, description, and inputSchema."""
        from agent_trace_intelligence.server import list_tools

        async def _check():
            return await list_tools()

        tools = asyncio.get_event_loop().run_until_complete(_check())
        for tool in tools:
            assert tool.name, f"Tool missing name"
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.inputSchema, f"Tool {tool.name} missing inputSchema"


class TestUnknownTool:
    def test_unknown_tool_returns_error(self):
        from agent_trace_intelligence.server import call_tool

        async def _check():
            return await call_tool("nonexistent_tool", {"trace": "{}"})

        result_list = asyncio.get_event_loop().run_until_complete(_check())
        assert len(result_list) == 1
        result = json.loads(result_list[0].text)
        assert result["error"] is True
        assert result["error_code"] == "UNKNOWN_TOOL"
