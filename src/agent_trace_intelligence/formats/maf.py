"""
Microsoft Agent Framework (MAF) GA 1.0 -> AgentTrace adapter.

MAF uses OpenTelemetry spans for tracing (OpenTelemetry GenAI Semantic Conventions).
Enable tracing in MAF with:
    from agent_framework.observability import configure_otel_providers
    configure_otel_providers(enable_sensitive_data=True)

Expected input: a list of OTel spans exported as dicts, or a dict with a "spans" key.

Each span has this shape:
    {
        "name": "invoke_agent Joker" | "chat gpt-4o" | "execute_tool search",
        "context": {"trace_id": "0x...", "span_id": "0x..."},
        "parent_id": "0x..." | null,
        "start_time": "2025-09-25T11:00:48.663688Z",
        "end_time":   "2025-09-25T11:00:57.271389Z",
        "status": {"status_code": "UNSET" | "OK" | "ERROR"},
        "attributes": {
            "gen_ai.operation.name":       "invoke_agent" | "chat" | "execute_tool",
            "gen_ai.agent.name":           "MyAgent",
            "gen_ai.request.instructions": "You are ...",
            "gen_ai.response.id":          "chatcmpl-...",
            "gen_ai.usage.input_tokens":   26,
            "gen_ai.usage.output_tokens":  29,
            "gen_ai.request.messages":     "<json string>",   # if enable_sensitive_data=True
            "gen_ai.response.message":     "<json string>",   # if enable_sensitive_data=True
        }
    }
"""
import json
from datetime import datetime
from typing import Any

from ..models.trace import AgentTrace, TraceStep, ToolCall


def _parse_ms(start: str, end: str) -> float | None:
    """Return duration in milliseconds between two ISO 8601 timestamps."""
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        s = datetime.strptime(start, fmt)
        e = datetime.strptime(end, fmt)
        return round((e - s).total_seconds() * 1000, 1)
    except Exception:
        return None


def _total_latency_ms(spans: list[dict]) -> float | None:
    """Sum of all span durations in milliseconds."""
    total = 0.0
    found = False
    for span in spans:
        ms = _parse_ms(span.get("start_time", ""), span.get("end_time", ""))
        if ms is not None:
            total += ms
            found = True
    return round(total, 1) if found else None


def adapt(raw: Any) -> AgentTrace:
    """
    Convert a MAF OpenTelemetry trace export to AgentTrace.

    Accepts:
    - A list of OTel span dicts (direct export from configure_otel_providers)
    - A dict with a "spans" key containing a list of span dicts
    - A dict with a "resourceSpans" key (OTLP JSON export format)

    Raises ValueError if the input shape is unrecognisable.
    """
    # Normalise input to a flat list of span dicts
    if isinstance(raw, list):
        spans = raw
    elif isinstance(raw, dict):
        if "spans" in raw:
            spans = raw["spans"]
        elif "resourceSpans" in raw:
            # OTLP JSON export format
            spans = []
            for resource_span in raw.get("resourceSpans", []):
                for scope_span in resource_span.get("scopeSpans", []):
                    spans.extend(scope_span.get("spans", []))
        else:
            raise ValueError(
                "Input does not look like a MAF OTel trace. "
                "Expected a list of spans, or a dict with a 'spans' or 'resourceSpans' key. "
                "Make sure you export traces with configure_otel_providers(enable_sensitive_data=True)."
            )
    else:
        raise ValueError(
            "Input must be a list of OTel spans or a dict with a 'spans' key. "
            "Got: " + type(raw).__name__
        )

    if not spans:
        raise ValueError(
            "MAF trace contains no spans. "
            "Ensure configure_otel_providers() is called before running the agent."
        )

    # Find root span (invoke_agent — parent_id is null)
    root_span = next(
        (s for s in spans if s.get("parent_id") is None),
        spans[0]
    )
    attrs = root_span.get("attributes", {})

    agent_name = attrs.get("gen_ai.agent.name") or attrs.get("gen_ai.agent.id")
    goal = attrs.get("gen_ai.request.instructions")
    trace_id = root_span.get("context", {}).get("trace_id")

    # Detect model from child chat spans
    model = None
    for span in spans:
        name = span.get("name", "")
        if name.startswith("chat "):
            model = name[len("chat "):]
            break

    # Aggregate token usage across all spans
    total_input = sum(
        int(s.get("attributes", {}).get("gen_ai.usage.input_tokens", 0))
        for s in spans
    )
    total_output = sum(
        int(s.get("attributes", {}).get("gen_ai.usage.output_tokens", 0))
        for s in spans
    )
    total_tokens = (total_input + total_output) or None

    # Sort child spans by start_time to build ordered steps
    child_spans = sorted(
        [s for s in spans if s.get("parent_id") is not None],
        key=lambda s: s.get("start_time", "")
    )

    steps: list[TraceStep] = []
    step_num = 1

    for span in child_spans:
        name = span.get("name", "")
        span_attrs = span.get("attributes", {})
        status = span.get("status", {}).get("status_code", "UNSET")
        latency = _parse_ms(span.get("start_time", ""), span.get("end_time", ""))
        token_count = (
            int(span_attrs.get("gen_ai.usage.input_tokens", 0)) +
            int(span_attrs.get("gen_ai.usage.output_tokens", 0))
        ) or None

        if name.startswith("execute_tool "):
            tool_name = name[len("execute_tool "):]

            # Parse tool input/output from attributes if sensitive data is enabled
            raw_args = span_attrs.get("gen_ai.tool.call.arguments", "{}")
            raw_result = span_attrs.get("gen_ai.tool.call.result", None)
            try:
                tool_input = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except (json.JSONDecodeError, TypeError):
                tool_input = {"raw": raw_args}

            error = None if status in ("UNSET", "OK") else f"Span status: {status}"

            steps.append(TraceStep(
                step_number=step_num,
                role="tool",
                timestamp=span.get("start_time"),
                tool_call=ToolCall(
                    tool_name=tool_name,
                    input=tool_input,
                    output=raw_result,
                    latency_ms=latency,
                    error=error,
                ),
            ))

        elif name.startswith("chat "):
            # Extract assistant response content if sensitive data was enabled
            content = None
            raw_response = span_attrs.get("gen_ai.response.message")
            if raw_response:
                try:
                    msg = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
                    if isinstance(msg, dict):
                        content = msg.get("content") or msg.get("text")
                    elif isinstance(msg, str):
                        content = msg
                except (json.JSONDecodeError, TypeError):
                    content = str(raw_response)

            steps.append(TraceStep(
                step_number=step_num,
                role="assistant",
                content=content,
                token_count=token_count,
                timestamp=span.get("start_time"),
            ))

        step_num += 1

    # Final output from last chat span response if available
    final_output = None
    for span in reversed(child_spans):
        raw_response = span.get("attributes", {}).get("gen_ai.response.message")
        if raw_response:
            try:
                msg = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
                if isinstance(msg, dict):
                    final_output = msg.get("content") or msg.get("text")
                elif isinstance(msg, str):
                    final_output = msg
            except (json.JSONDecodeError, TypeError):
                pass
            if final_output:
                break

    return AgentTrace(
        trace_id=trace_id,
        agent_name=agent_name,
        goal=goal,
        model=model,
        steps=steps,
        total_tokens=total_tokens,
        total_latency_ms=_total_latency_ms(spans),
        final_output=final_output,
    )
