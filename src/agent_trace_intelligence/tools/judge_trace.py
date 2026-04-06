import json
from pydantic import ValidationError

from ..models.trace import AgentTrace
from ..judge.llm_judge import call_judge

JUDGE_TRACE_SYSTEM = """
You are an expert AI agent debugger. Your job is to diagnose why an agent behaved the way it did and identify how to fix it.

Score the agent on four dimensions:
1. goal_completion (0.0-1.0): Did the agent fully achieve the stated goal?
2. reasoning_clarity (0.0-1.0): Were the agent's reasoning steps logical and easy to follow?
3. tool_usage (0.0-1.0): Did the agent use the right tools, in the right order, without redundancy?
4. output_quality (0.0-1.0): Was the final output accurate, complete, and well-formed?

Overall score = average of the four dimensions above.

Grade mapping — use A/B/C/D/F only, no +/- variants:
- 0.9+ = A
- 0.8-0.89 = B
- 0.7-0.79 = C
- 0.6-0.69 = D
- below 0.6 = F

Verdict mapping:
- overall_score >= 0.85 → "production-ready"
- overall_score 0.6-0.84 → "needs optimisation"
- overall_score < 0.6 → "broken"

root_causes: Identify 1-3 specific causal explanations for why the agent underperformed. Focus on WHY something went wrong, not just what went wrong. Be specific to this trace — reference step numbers and tool names. If the agent performed well, return an empty list.

explain_like_im_5: One plain-English sentence a non-technical person could understand. No jargon. Describe what the agent did wrong (or right) as if explaining to someone who has never heard of AI agents.

Respond with valid JSON only matching this exact shape:
{
  "overall_score": 0.82,
  "grade": "B",
  "verdict": "needs optimisation",
  "dimension_scores": {
    "goal_completion": 0.9,
    "reasoning_clarity": 0.8,
    "tool_usage": 0.75,
    "output_quality": 0.83
  },
  "summary": "One sentence summary of agent performance",
  "root_causes": ["specific causal explanation referencing step/tool", "second cause if applicable"],
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1"],
  "recommendation": "One concrete actionable improvement",
  "explain_like_im_5": "Plain English sentence for non-technical readers",
  "confidence": "high"
}
"""


def build_judge_prompt(trace: AgentTrace, goal: str = None) -> str:
    effective_goal = goal or trace.goal or "Not specified"
    return f"""
Agent goal: {effective_goal}
Agent name: {trace.agent_name or "Unknown"}
Model used: {trace.model or "Unknown"}
Total steps: {len(trace.steps)}
Total tokens: {trace.total_tokens or "Not recorded"}

Trace steps:
{json.dumps([s.model_dump() for s in trace.steps], indent=2)}

Final output:
{trace.final_output or "Not recorded"}

Evaluate this trace and return your assessment as JSON.
"""


async def judge_trace(trace_json: str, goal: str = None) -> str:
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
        result = await call_judge(JUDGE_TRACE_SYSTEM, build_judge_prompt(trace, goal))
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
