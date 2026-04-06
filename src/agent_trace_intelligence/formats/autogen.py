"""
AutoGen (legacy pyautogen) message history → AgentTrace adapter.
Works on raw dicts/lists — does NOT import pyautogen as a dependency.
"""
from ..models.trace import AgentTrace, TraceStep


def adapt(raw) -> AgentTrace:
    """
    Convert AutoGen message history to AgentTrace.

    Accepts two input shapes:
    1. A list of message dicts (direct message history):
       [{"role": "user", "content": "...", "name": "..."}, ...]

    2. A dict with a "messages" key:
       {"messages": [...], "config_list": [{"model": "gpt-4o", ...}]}
    """
    messages = None
    model = None
    config_list = None

    if isinstance(raw, list):
        messages = raw
    elif isinstance(raw, dict):
        if "messages" in raw:
            messages = raw["messages"]
            config_list = raw.get("config_list", [])
            if config_list and isinstance(config_list, list) and len(config_list) > 0:
                model = config_list[0].get("model")
        else:
            raise ValueError(
                "Input does not look like an AutoGen trace — expected a list of messages "
                "or a dict with a 'messages' key"
            )
    else:
        raise ValueError(
            "Input does not look like an AutoGen trace — expected a list of messages "
            "or a dict with a 'messages' key"
        )

    if not isinstance(messages, list):
        raise ValueError("AutoGen messages must be a list")

    if not messages:
        raise ValueError("AutoGen trace contains no messages to convert")

    steps = []
    goal = None

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue

        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        name = msg.get("name")

        # Map AutoGen roles to AgentTrace roles
        if role in ("user", "human"):
            mapped_role = "user"
        elif role in ("assistant", "ai", "agent"):
            mapped_role = "assistant"
        elif role == "function" or role == "tool":
            mapped_role = "tool"
        else:
            mapped_role = "assistant"

        # Extract goal from first user message
        if goal is None and mapped_role == "user" and content:
            goal = str(content)

        step = TraceStep(
            step_number=i + 1,
            role=mapped_role,
            content=str(content) if content else None,
        )
        steps.append(step)

    if not steps:
        raise ValueError("AutoGen trace contains no valid steps to convert")

    # Final output from last assistant message
    final_output = None
    for step in reversed(steps):
        if step.role == "assistant" and step.content:
            final_output = step.content
            break

    return AgentTrace(
        goal=goal,
        model=model,
        steps=steps,
        final_output=final_output,
    )
