import json
from pydantic import ValidationError

from ..models.trace import AgentTrace
from ..judge.llm_judge import call_judge

TRACE_BREAKDOWN_SYSTEM = """
You are an expert AI agent debugger. Your job is to diagnose each step of an agent execution trace and identify where and why things went wrong.

For each step, assign:
- score: float 0.0-1.0 (1.0 = perfect decision, 0.0 = harmful/wrong)
- assessment: one sentence explanation
- flag: one of [REDUNDANT_TOOL_CALL, HALLUCINATED_TOOL, REASONING_GAP, GOAL_DRIFT, PREMATURE_STOP] or null

Flag definitions:
- REDUNDANT_TOOL_CALL: tool called with identical or near-identical input as a previous step
- HALLUCINATED_TOOL: assistant references or calls a tool that does not appear anywhere in the trace
- REASONING_GAP: assistant output in this step does not logically follow from the previous tool result
- GOAL_DRIFT: this step moves away from the original stated goal
- PREMATURE_STOP: this is the final step but the goal is clearly not yet achieved

Respond with valid JSON only matching this exact shape:
{
  "steps": [
    {"step_number": 1, "description": "...", "score": 0.9, "assessment": "...", "flag": null}
  ],
  "flags_summary": ["REDUNDANT_TOOL_CALL"],
  "worst_step": 4,
  "best_step": 1
}
"""


def build_breakdown_user_prompt(trace: AgentTrace) -> str:
    return f"""
Agent goal: {trace.goal or 'Not specified'}

Trace steps:
{json.dumps([s.model_dump() for s in trace.steps], indent=2)}

Score every step. Apply flags strictly only when the definition is clearly met.
"""


async def trace_breakdown(trace_json: str) -> str:
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

    try:
        result = await call_judge(TRACE_BREAKDOWN_SYSTEM, build_breakdown_user_prompt(trace))
        return json.dumps(result)
    except Exception as e:
        return json.dumps(
            {
                "error": True,
                "error_code": "JUDGE_FAILED",
                "error_message": "LLM judge call failed",
                "detail": str(e),
            }
        )
