"""
Tests for format adapters — no API key needed, runs in CI.
"""
import json
import os
import pytest

from agent_trace_intelligence.formats import (
    adapt_langchain,
    adapt_openai_agents,
    adapt_maf,
    adapt_autogen,
)
from agent_trace_intelligence.models.trace import AgentTrace


def load_fixture(filename: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "sample_traces", filename)
    with open(path) as f:
        return json.load(f)


class TestLangChainAdapter:
    def test_adapt_langchain_valid_input_returns_agent_trace(self):
        raw = load_fixture("langchain_raw.json")
        result = adapt_langchain(raw)
        assert isinstance(result, AgentTrace)

    def test_adapt_langchain_valid_input_has_steps(self):
        raw = load_fixture("langchain_raw.json")
        result = adapt_langchain(raw)
        assert len(result.steps) > 0

    def test_adapt_langchain_bad_input_raises_value_error(self):
        with pytest.raises(ValueError, match="runs"):
            adapt_langchain({})

    def test_adapt_langchain_no_runs_key_raises(self):
        with pytest.raises(ValueError):
            adapt_langchain({"messages": [], "model": "gpt-4o"})

    def test_adapt_langchain_step_roles_valid(self):
        raw = load_fixture("langchain_raw.json")
        result = adapt_langchain(raw)
        valid_roles = {"user", "assistant", "tool"}
        for step in result.steps:
            assert step.role in valid_roles


class TestOpenAIAgentsAdapter:
    def test_adapt_openai_agents_valid_input_returns_agent_trace(self):
        raw = load_fixture("openai_agents_raw.json")
        result = adapt_openai_agents(raw)
        assert isinstance(result, AgentTrace)

    def test_adapt_openai_agents_valid_input_has_steps(self):
        raw = load_fixture("openai_agents_raw.json")
        result = adapt_openai_agents(raw)
        assert len(result.steps) > 0

    def test_adapt_openai_agents_extracts_total_tokens(self):
        raw = load_fixture("openai_agents_raw.json")
        result = adapt_openai_agents(raw)
        assert result.total_tokens == 475

    def test_adapt_openai_agents_bad_input_raises_value_error(self):
        with pytest.raises(ValueError, match="steps"):
            adapt_openai_agents({"id": "run_123", "instructions": "test"})

    def test_adapt_openai_agents_extracts_tool_calls(self):
        raw = load_fixture("openai_agents_raw.json")
        result = adapt_openai_agents(raw)
        tool_steps = [s for s in result.steps if s.tool_call is not None]
        assert len(tool_steps) > 0


class TestMAFAdapter:
    def test_adapt_maf_valid_input_returns_agent_trace(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        assert isinstance(result, AgentTrace)

    def test_adapt_maf_valid_input_has_steps(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        assert len(result.steps) > 0

    def test_adapt_maf_extracts_agent_name(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        assert result.agent_name == "ResearchAgent"

    def test_adapt_maf_extracts_goal(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        assert result.goal is not None
        assert len(result.goal) > 0

    def test_adapt_maf_extracts_model(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        assert result.model == "gpt-4o"

    def test_adapt_maf_extracts_tool_calls(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        tool_steps = [s for s in result.steps if s.tool_call is not None]
        assert len(tool_steps) > 0

    def test_adapt_maf_extracts_total_tokens(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw)
        assert result.total_tokens == 520  # 85+45+210+180

    def test_adapt_maf_accepts_list_of_spans(self):
        raw = load_fixture("maf_raw.json")
        result = adapt_maf(raw["spans"])
        assert isinstance(result, AgentTrace)

    def test_adapt_maf_bad_input_raises_value_error(self):
        with pytest.raises(ValueError):
            adapt_maf({"placeholder": True})

    def test_adapt_maf_empty_spans_raises_value_error(self):
        with pytest.raises(ValueError):
            adapt_maf({"spans": []})


class TestAutoGenAdapter:
    def test_adapt_autogen_valid_input_returns_agent_trace(self):
        raw = load_fixture("autogen_raw.json")
        result = adapt_autogen(raw)
        assert isinstance(result, AgentTrace)

    def test_adapt_autogen_valid_input_has_steps(self):
        raw = load_fixture("autogen_raw.json")
        result = adapt_autogen(raw)
        assert len(result.steps) > 0

    def test_adapt_autogen_extracts_model(self):
        raw = load_fixture("autogen_raw.json")
        result = adapt_autogen(raw)
        assert result.model == "gpt-4o"

    def test_adapt_autogen_extracts_goal_from_first_user_message(self):
        raw = load_fixture("autogen_raw.json")
        result = adapt_autogen(raw)
        assert result.goal is not None
        assert "Fibonacci" in result.goal

    def test_adapt_autogen_bad_input_raises_value_error(self):
        with pytest.raises(ValueError):
            adapt_autogen({"no_messages_key": True})

    def test_adapt_autogen_accepts_list_directly(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = adapt_autogen(messages)
        assert isinstance(result, AgentTrace)
        assert len(result.steps) == 2

    def test_adapt_autogen_empty_messages_raises(self):
        with pytest.raises(ValueError):
            adapt_autogen({"messages": []})
