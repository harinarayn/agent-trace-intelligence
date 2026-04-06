"""
Tests for efficiency_score tool — deterministic, no API key needed.
All tests run in CI.
"""
import asyncio
import json
import os
import pytest

from agent_trace_intelligence.tools.efficiency_score import efficiency_score


def load_trace(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "sample_traces", filename)
    with open(path) as f:
        return f.read()


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestGoodTrace:
    def test_good_trace_scores_high(self):
        result = json.loads(run(efficiency_score(load_trace("good_trace.json"))))
        assert result["overall_efficiency_score"] >= 0.8, (
            f"Expected good_trace score >= 0.8, got {result['overall_efficiency_score']}"
        )

    def test_good_trace_no_redundant_calls(self):
        result = json.loads(run(efficiency_score(load_trace("good_trace.json"))))
        assert result["tool_efficiency"]["redundant_calls"] == 0


class TestBadTrace:
    def test_bad_trace_scores_low(self):
        result = json.loads(run(efficiency_score(load_trace("bad_trace.json"))))
        assert result["overall_efficiency_score"] < 0.6, (
            f"Expected bad_trace score < 0.6, got {result['overall_efficiency_score']}"
        )

    def test_bad_trace_redundant_calls_is_one(self):
        result = json.loads(run(efficiency_score(load_trace("bad_trace.json"))))
        assert result["tool_efficiency"]["redundant_calls"] == 1, (
            f"Expected 1 redundant call, got {result['tool_efficiency']['redundant_calls']}"
        )


class TestInefficientTrace:
    def test_inefficient_trace_scores_low(self):
        result = json.loads(run(efficiency_score(load_trace("inefficient_trace.json"))))
        assert result["overall_efficiency_score"] <= 0.4, (
            f"Expected inefficient_trace score <= 0.4, got {result['overall_efficiency_score']}"
        )

    def test_inefficient_trace_high_token_rating(self):
        result = json.loads(run(efficiency_score(load_trace("inefficient_trace.json"))))
        # 3200 tokens / 7 steps = 457.1 tps → "moderate"
        assert result["token_efficiency"]["rating"] in ("moderate", "high")

    def test_inefficient_trace_poor_tool_rating(self):
        result = json.loads(run(efficiency_score(load_trace("inefficient_trace.json"))))
        assert result["tool_efficiency"]["rating"] == "poor"

    def test_inefficient_trace_slow_latency(self):
        result = json.loads(run(efficiency_score(load_trace("inefficient_trace.json"))))
        assert result["latency"]["rating"] == "slow"


class TestMissingData:
    def test_missing_token_data_returns_null(self):
        trace = json.dumps({
            "steps": [
                {"step_number": 1, "role": "user", "content": "hello"}
            ]
        })
        result = json.loads(run(efficiency_score(trace)))
        assert result["token_efficiency"]["tokens_per_step"] is None
        assert result["token_efficiency"]["total_tokens"] is None

    def test_missing_token_data_does_not_crash(self):
        trace = json.dumps({
            "steps": [
                {"step_number": 1, "role": "user", "content": "hello"}
            ]
        })
        # Should not raise
        result = json.loads(run(efficiency_score(trace)))
        assert "overall_efficiency_score" in result

    def test_missing_latency_returns_null_slowest_step(self):
        trace = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "role": "tool",
                    "tool_call": {
                        "tool_name": "search",
                        "input": {"query": "test"},
                        "output": "result"
                    }
                }
            ]
        })
        result = json.loads(run(efficiency_score(trace)))
        assert result["latency"]["slowest_step"] is None
        assert result["latency"]["slowest_tool"] is None

    def test_missing_latency_does_not_crash(self):
        trace = json.dumps({
            "steps": [
                {"step_number": 1, "role": "user", "content": "hello"}
            ]
        })
        result = json.loads(run(efficiency_score(trace)))
        assert "latency" in result


class TestRedundantAndFailedCalls:
    def test_redundant_calls_detected(self):
        trace = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "role": "tool",
                    "tool_call": {"tool_name": "search", "input": {"q": "test"}, "output": "result1"}
                },
                {
                    "step_number": 2,
                    "role": "tool",
                    "tool_call": {"tool_name": "search", "input": {"q": "test"}, "output": "result1"}
                }
            ]
        })
        result = json.loads(run(efficiency_score(trace)))
        assert result["tool_efficiency"]["redundant_calls"] > 0

    def test_failed_calls_counted(self):
        trace = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "role": "tool",
                    "tool_call": {
                        "tool_name": "search",
                        "input": {"q": "test"},
                        "output": None,
                        "error": "Connection timeout"
                    }
                }
            ]
        })
        result = json.loads(run(efficiency_score(trace)))
        assert result["tool_efficiency"]["failed_calls"] == 1


class TestErrorContracts:
    def test_empty_trace_returns_error(self):
        trace = json.dumps({"steps": []})
        result = json.loads(run(efficiency_score(trace)))
        assert result["error"] is True
        assert result["error_code"] == "EMPTY_TRACE"

    def test_invalid_json_returns_error(self):
        result = json.loads(run(efficiency_score("not valid json {")))
        assert result["error"] is True
        assert result["error_code"] == "PARSE_ERROR"

    def test_json_array_returns_invalid_trace_error(self):
        result = json.loads(run(efficiency_score("[1, 2, 3]")))
        assert result["error"] is True
        assert result["error_code"] == "INVALID_TRACE"

    def test_missing_steps_returns_invalid_trace_error(self):
        result = json.loads(run(efficiency_score('{"goal": "test"}')))
        assert result["error"] is True
        assert result["error_code"] == "INVALID_TRACE"
