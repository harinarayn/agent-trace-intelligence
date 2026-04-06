"""
OpenAI Agents SDK trace output → AgentTrace adapter.
Works on raw dicts — does NOT import openai-agents as a dependency.
"""
from ..models.trace import AgentTrace, TraceStep, ToolCall


def adapt(raw: dict) -> AgentTrace:
    """
    Convert OpenAI Agents SDK trace output to AgentTrace.

    Expected input shape:
    {
        "id": "run_abc123",
        "instructions": "You are a helpful assistant...",
        "model": "gpt-4o",
        "steps": [
            {
                "id": "step_001",
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_xyz",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": "{\"query\": \"...\"}"
                        },
                        "output": "...",
                        "latency_ms": 1200
                    }
                ]
            },
            {
                "id": "step_002",
                "type": "message_creation",
                "message": {
                    "role": "assistant",
                    "content": "Based on my research..."
                }
            }
        ],
        "usage": {
            "prompt_tokens": 450,
            "completion_tokens": 120,
            "total_tokens": 570
        }
    }
    """
    if "steps" not in raw:
        raise ValueError(
            "Input does not look like an OpenAI Agents SDK trace — expected 'steps' key at top level"
        )

    if not isinstance(raw["steps"], list):
        raise ValueError("'steps' must be a list of RunStep objects")

    steps = []
    step_counter = 0

    for run_step in raw["steps"]:
        step_type = run_step.get("type", "")

        if step_type == "tool_calls":
            tool_calls = run_step.get("tool_calls", [])
            for tc in tool_calls:
                step_counter += 1
                fn = tc.get("function", {})
                tool_name = fn.get("name", tc.get("type", "unknown_tool"))

                # Parse arguments — may be JSON string or dict
                raw_args = fn.get("arguments", {})
                if isinstance(raw_args, str):
                    import json
                    try:
                        tool_input = json.loads(raw_args)
                    except Exception:
                        tool_input = {"raw_arguments": raw_args}
                elif isinstance(raw_args, dict):
                    tool_input = raw_args
                else:
                    tool_input = {"arguments": str(raw_args)}

                tool_output = tc.get("output")
                latency_ms = tc.get("latency_ms")
                error = tc.get("error")

                steps.append(
                    TraceStep(
                        step_number=step_counter,
                        role="tool",
                        tool_call=ToolCall(
                            tool_name=tool_name,
                            input=tool_input,
                            output=tool_output,
                            latency_ms=latency_ms,
                            error=str(error) if error else None,
                        ),
                    )
                )

        elif step_type == "message_creation":
            step_counter += 1
            message = run_step.get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                # OpenAI content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", {}).get("value", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = " ".join(text_parts)

            steps.append(
                TraceStep(
                    step_number=step_counter,
                    role=message.get("role", "assistant"),
                    content=str(content) if content else None,
                )
            )

        else:
            # Unknown step type — add as assistant step with raw content
            step_counter += 1
            steps.append(
                TraceStep(
                    step_number=step_counter,
                    role="assistant",
                    content=str(run_step),
                )
            )

    if not steps:
        raise ValueError("OpenAI Agents trace contains no steps to convert")

    # Extract usage
    usage = raw.get("usage", {})
    total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None

    return AgentTrace(
        trace_id=raw.get("id"),
        goal=raw.get("instructions"),
        model=raw.get("model"),
        steps=steps,
        total_tokens=total_tokens,
        final_output=raw.get("final_output"),
    )
