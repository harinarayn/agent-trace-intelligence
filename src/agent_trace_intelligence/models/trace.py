from pydantic import BaseModel
from typing import Optional, List, Any


class ToolCall(BaseModel):
    tool_name: str
    input: dict
    output: Any
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class TraceStep(BaseModel):
    step_number: int
    role: str  # "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    token_count: Optional[int] = None
    timestamp: Optional[str] = None


class AgentTrace(BaseModel):
    trace_id: Optional[str] = None
    agent_name: Optional[str] = None
    goal: Optional[str] = None  # What was the agent trying to do?
    steps: List[TraceStep]
    total_tokens: Optional[int] = None
    total_latency_ms: Optional[float] = None
    final_output: Optional[str] = None
    model: Optional[str] = None
