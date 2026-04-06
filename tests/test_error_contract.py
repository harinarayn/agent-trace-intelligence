"""
Tests for error response contract — validates all error shapes.
No API key needed, runs in CI.
"""
import asyncio
import json
import pytest

from agent_trace_intelligence.tools.efficiency_score import efficiency_score
from agent_trace_intelligence.tools.judge_trace import judge_trace
from agent_trace_intelligence.tools.trace_breakdown import trace_breakdown


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


TOOLS = [efficiency_score, judge_trace, trace_breakdown]
TOOL_NAMES = ["efficiency_score", "judge_trace", "trace_breakdown"]


class TestAllToolsReturnString:
    def test_efficiency_score_returns_string(self):
        result = run(efficiency_score("not valid json"))
        assert isinstance(result, str)

    def test_judge_trace_returns_string(self):
        result = run(judge_trace("not valid json"))
        assert isinstance(result, str)

    def test_trace_breakdown_returns_string(self):
        result = run(trace_breakdown("not valid json"))
        assert isinstance(result, str)

    def test_efficiency_score_never_raises(self):
        # Should never raise even with bad input
        result = run(efficiency_score("{bad json"))
        assert isinstance(result, str)


class TestErrorShape:
    """All error responses must have error, error_code, error_message keys."""

    def _assert_error_shape(self, result_str: str):
        result = json.loads(result_str)
        assert "error" in result, f"Missing 'error' key in: {result}"
        assert "error_code" in result, f"Missing 'error_code' key in: {result}"
        assert "error_message" in result, f"Missing 'error_message' key in: {result}"
        assert result["error"] is True, f"Expected error=True (boolean), got: {result['error']}"

    def test_parse_error_shape_efficiency_score(self):
        self._assert_error_shape(run(efficiency_score("invalid json {")))

    def test_parse_error_shape_judge_trace(self):
        self._assert_error_shape(run(judge_trace("invalid json {")))

    def test_parse_error_shape_trace_breakdown(self):
        self._assert_error_shape(run(trace_breakdown("invalid json {")))

    def test_invalid_trace_shape_efficiency_score(self):
        self._assert_error_shape(run(efficiency_score('{"goal": "no steps field"}')))

    def test_invalid_trace_shape_judge_trace(self):
        self._assert_error_shape(run(judge_trace('{"goal": "no steps field"}')))

    def test_empty_trace_shape_efficiency_score(self):
        self._assert_error_shape(run(efficiency_score('{"steps": []}')))

    def test_empty_trace_shape_judge_trace(self):
        self._assert_error_shape(run(judge_trace('{"steps": []}')))


class TestParseError:
    def test_invalid_json_returns_parse_error_efficiency_score(self):
        result = json.loads(run(efficiency_score("not valid json {")))
        assert result["error_code"] == "PARSE_ERROR"

    def test_invalid_json_returns_parse_error_judge_trace(self):
        result = json.loads(run(judge_trace("{broken")))
        assert result["error_code"] == "PARSE_ERROR"

    def test_invalid_json_returns_parse_error_trace_breakdown(self):
        result = json.loads(run(trace_breakdown("{broken")))
        assert result["error_code"] == "PARSE_ERROR"


class TestEmptyTrace:
    def test_empty_steps_returns_empty_trace_error(self):
        result = json.loads(run(efficiency_score('{"steps": []}')))
        assert result["error"] is True
        assert result["error_code"] == "EMPTY_TRACE"

    def test_empty_trace_judge_trace(self):
        result = json.loads(run(judge_trace('{"steps": []}')))
        assert result["error"] is True
        assert result["error_code"] == "EMPTY_TRACE"

    def test_empty_trace_trace_breakdown(self):
        result = json.loads(run(trace_breakdown('{"steps": []}')))
        assert result["error"] is True
        assert result["error_code"] == "EMPTY_TRACE"


class TestInvalidTrace:
    def test_missing_steps_field_returns_invalid_trace(self):
        result = json.loads(run(efficiency_score('{"goal": "test", "agent_name": "bot"}')))
        assert result["error"] is True
        assert result["error_code"] == "INVALID_TRACE"

    def test_non_object_json_returns_invalid_trace(self):
        result = json.loads(run(efficiency_score("[1, 2, 3]")))
        assert result["error"] is True
        assert result["error_code"] == "INVALID_TRACE"

    def test_non_object_json_judge_trace(self):
        result = json.loads(run(judge_trace('"just a string"')))
        assert result["error"] is True
        assert result["error_code"] == "INVALID_TRACE"

    def test_wrong_type_for_steps_returns_invalid_trace(self):
        result = json.loads(run(efficiency_score('{"steps": "not a list"}')))
        assert result["error"] is True
        assert result["error_code"] == "INVALID_TRACE"
