"""
LangChain callback handler output → AgentTrace adapter.
Works on raw dicts — does NOT import langchain as a dependency.
"""
from ..models.trace import AgentTrace, TraceStep, ToolCall


def adapt(raw: dict) -> AgentTrace:
    """
    Convert LangChain callback handler output or LangSmith trace export to AgentTrace.

    Expected input shape:
    {
        "runs": [
            {
                "id": "...",
                "name": "...",
                "run_type": "tool" | "llm" | "chain",
                "inputs": {...},
                "outputs": {...},
                "start_time": "...",
                "end_time": "...",
                "error": null | "..."
            },
            ...
        ]
    }
    """
    if "runs" not in raw:
        raise ValueError(
            "Input does not look like a LangChain trace — expected 'runs' key at top level"
        )

    runs = raw["runs"]
    if not isinstance(runs, list):
        raise ValueError("'runs' must be a list of run objects")

    steps = []
    goal = None
    agent_name = None
    model = None
    total_tokens = None

    for i, run in enumerate(runs):
        run_type = run.get("run_type", "")
        name = run.get("name", "")
        inputs = run.get("inputs", {})
        outputs = run.get("outputs", {})
        error = run.get("error")

        # Extract goal from first chain input
        if goal is None and run_type == "chain":
            if isinstance(inputs, dict):
                goal = inputs.get("input") or inputs.get("query") or inputs.get("question")
                if isinstance(goal, dict):
                    goal = str(goal)

        # Extract model name from LLM runs
        if model is None and run_type == "llm":
            model = run.get("serialized", {}).get("id", [None])[-1]
            agent_name = agent_name or name

        # Extract token usage from LLM runs
        if run_type == "llm" and outputs:
            llm_output = outputs.get("llm_output", {})
            if llm_output:
                usage = llm_output.get("token_usage", {})
                if usage and total_tokens is None:
                    total_tokens = usage.get("total_tokens")

        # Compute latency
        latency_ms = None
        start_time = run.get("start_time")
        end_time = run.get("end_time")
        if start_time and end_time:
            try:
                from datetime import datetime
                fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
                try:
                    s = datetime.strptime(start_time, fmt)
                    e = datetime.strptime(end_time, fmt)
                except ValueError:
                    fmt2 = "%Y-%m-%dT%H:%M:%SZ"
                    s = datetime.strptime(start_time, fmt2)
                    e = datetime.strptime(end_time, fmt2)
                latency_ms = (e - s).total_seconds() * 1000
            except Exception:
                pass

        if run_type == "tool":
            tool_input = inputs if isinstance(inputs, dict) else {"input": str(inputs)}
            tool_output = outputs if not isinstance(outputs, dict) else outputs.get("output", outputs)
            step = TraceStep(
                step_number=i + 1,
                role="tool",
                content=None,
                tool_call=ToolCall(
                    tool_name=name,
                    input=tool_input,
                    output=tool_output,
                    latency_ms=latency_ms,
                    error=str(error) if error else None,
                ),
                timestamp=start_time,
            )
        elif run_type == "llm":
            content = None
            if outputs:
                generations = outputs.get("generations", [[]])
                if generations and generations[0]:
                    first_gen = generations[0][0]
                    if isinstance(first_gen, dict):
                        content = first_gen.get("text") or str(first_gen)
                    else:
                        content = str(first_gen)
            step = TraceStep(
                step_number=i + 1,
                role="assistant",
                content=content,
                timestamp=start_time,
            )
        else:
            # chain or other — treat as assistant step
            content = str(outputs) if outputs else None
            step = TraceStep(
                step_number=i + 1,
                role="assistant",
                content=content,
                timestamp=start_time,
            )

        steps.append(step)

    if not steps:
        raise ValueError("LangChain trace contains no runs to convert")

    return AgentTrace(
        agent_name=agent_name,
        goal=goal,
        steps=steps,
        total_tokens=total_tokens,
        model=model,
    )
