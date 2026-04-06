import json
from pydantic import ValidationError

from ..models.trace import AgentTrace, TraceStep

# String rating → numeric score mapping (used for weighted average)
RATING_SCORES = {
    "good": 1.0,
    "moderate": 0.6,
    "acceptable": 0.6,  # latency-specific alias for moderate
    "poor": 0.2,
    "high": 0.2,        # token-specific alias for poor
    "fast": 1.0,        # latency-specific alias for good
    "slow": 0.2,        # latency-specific alias for poor
}

TOKEN_ADVICE = {
    "good": "Token usage is efficient — no action needed",
    "moderate": "Consider compressing tool outputs before passing to next step",
    "high": "Token usage is very high — compress tool outputs and reduce system prompt verbosity",
}


def rate_tokens_per_step(tps: float) -> str:
    if tps < 300:
        return "good"
    if tps <= 600:
        return "moderate"
    return "high"


def rate_redundancy(rate: float) -> str:
    if rate < 0.1:
        return "good"
    if rate <= 0.25:
        return "moderate"
    return "poor"


def rate_latency(ms: float) -> str:
    if ms < 5000:
        return "fast"
    if ms <= 15000:
        return "acceptable"
    return "slow"


def compute_overall_efficiency(token_rating: str, tool_rating: str, latency_rating: str) -> float:
    # Weighted average: tokens 40%, tools 40%, latency 20%
    token_score = RATING_SCORES.get(token_rating, 0.5)
    tool_score = RATING_SCORES.get(tool_rating, 0.5)
    latency_score = RATING_SCORES.get(latency_rating, 0.5)
    return round((token_score * 0.4) + (tool_score * 0.4) + (latency_score * 0.2), 2)


def detect_redundant_calls(steps: list) -> int:
    seen = []
    redundant = 0
    for step in steps:
        if step.tool_call:
            key = (step.tool_call.tool_name, json.dumps(step.tool_call.input, sort_keys=True))
            if key in seen:
                redundant += 1
            else:
                seen.append(key)
    return redundant


def compute_tokens(trace: AgentTrace) -> tuple:
    """Returns (total_tokens, tokens_per_step). Either can be None if data unavailable."""
    step_count = len(trace.steps)

    # Priority 1: use AgentTrace.total_tokens if present
    if trace.total_tokens is not None:
        return trace.total_tokens, round(trace.total_tokens / step_count, 1)

    # Priority 2: sum TraceStep.token_count where available
    step_tokens = [s.token_count for s in trace.steps if s.token_count is not None]
    if step_tokens:
        total = sum(step_tokens)
        return total, round(total / step_count, 1)

    # Priority 3: no data available
    return None, None


async def efficiency_score(trace_json: str) -> str:
    try:
        trace_data = json.loads(trace_json)
    except json.JSONDecodeError as e:
        return json.dumps(
            {
                "error": True,
                "error_code": "PARSE_ERROR",
                "error_message": "Input is not valid JSON",
                "detail": str(e),
            }
        )

    if not isinstance(trace_data, dict):
        return json.dumps(
            {
                "error": True,
                "error_code": "INVALID_TRACE",
                "error_message": "Trace must be a JSON object, not an array or primitive",
            }
        )

    try:
        trace = AgentTrace(**trace_data)
    except ValidationError as e:
        return json.dumps(
            {
                "error": True,
                "error_code": "INVALID_TRACE",
                "error_message": "Trace failed schema validation",
                "detail": str(e),
            }
        )

    if not trace.steps:
        return json.dumps(
            {
                "error": True,
                "error_code": "EMPTY_TRACE",
                "error_message": "Trace contains no steps to evaluate",
            }
        )

    # --- Token efficiency ---
    total_tokens, tokens_per_step = compute_tokens(trace)
    if tokens_per_step is not None:
        token_rating = rate_tokens_per_step(tokens_per_step)
    else:
        token_rating = "acceptable"

    token_advice = TOKEN_ADVICE.get(token_rating, "")

    # --- Tool efficiency ---
    tool_steps = [s for s in trace.steps if s.tool_call is not None]
    total_tool_calls = len(tool_steps)
    redundant_calls = detect_redundant_calls(trace.steps)
    failed_calls = sum(1 for s in tool_steps if s.tool_call.error is not None)

    if total_tool_calls > 0:
        redundancy_rate = round(redundant_calls / total_tool_calls, 2)
        tool_rating = rate_redundancy(redundancy_rate)
    else:
        redundancy_rate = 0.0
        tool_rating = "good"

    # --- Latency ---
    latency_steps = [(s.step_number, s.tool_call) for s in trace.steps if s.tool_call and s.tool_call.latency_ms is not None]

    if latency_steps or trace.total_latency_ms is not None:
        if trace.total_latency_ms is not None:
            total_ms = trace.total_latency_ms
        else:
            total_ms = sum(tc.latency_ms for _, tc in latency_steps)

        latency_rating = rate_latency(total_ms)

        if latency_steps:
            slowest = max(latency_steps, key=lambda x: x[1].latency_ms)
            slowest_step = slowest[0]
            slowest_tool = slowest[1].tool_name
        else:
            slowest_step = None
            slowest_tool = None
    else:
        total_ms = None
        slowest_step = None
        slowest_tool = None
        latency_rating = "acceptable"

    # --- Overall score ---
    overall = compute_overall_efficiency(token_rating, tool_rating, latency_rating)

    result = {
        "token_efficiency": {
            "total_tokens": total_tokens,
            "tokens_per_step": tokens_per_step,
            "rating": token_rating,
            "advice": token_advice,
        },
        "tool_efficiency": {
            "total_tool_calls": total_tool_calls,
            "redundant_calls": redundant_calls,
            "failed_calls": failed_calls,
            "redundancy_rate": redundancy_rate,
            "rating": tool_rating,
        },
        "latency": {
            "total_ms": total_ms,
            "slowest_step": slowest_step,
            "slowest_tool": slowest_tool,
            "rating": latency_rating,
        },
        "overall_efficiency_score": overall,
    }

    return json.dumps(result)
