# Agent Trace Intelligence MCP Server — Build Spec v1.0
> Ready to paste into Claude Code

---

## Overview

Build a Python-based MCP server called **agent-trace-intelligence** that helps developers diagnose why an agent behaved the way it did — and how to fix it. Zero instrumentation required — just pass a trace JSON and get root causes, scores, and actionable fixes back.

**Positioning:** "Diagnose why your agent did what it did — and how to fix it."

---

## Tech Stack

- **Language:** Python 3.11+
- **MCP SDK:** `mcp` (official Python MCP SDK)
- **LLM Judge:** `litellm` (model-agnostic — supports Azure OpenAI, OpenAI, Anthropic)
- **Validation:** `pydantic` v2
- **Package manager:** `uv`
- **Transport:** stdio (default), SSE (optional)

---

## Project Structure

```
agent-trace-intelligence/
├── src/
│   └── agent_trace_intelligence/
│       ├── __init__.py
│       ├── server.py          # MCP server entrypoint
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── judge_trace.py       # Tool 1
│       │   ├── trace_breakdown.py   # Tool 2
│       │   └── efficiency_score.py  # Tool 3
│       ├── models/
│       │   ├── __init__.py
│       │   └── trace.py       # Pydantic trace schema
│       ├── formats/
│       │   ├── __init__.py          # exports all adapt functions
│       │   ├── langchain.py         # LangChain → AgentTrace adapter
│       │   ├── openai_agents.py     # OpenAI Agents SDK → AgentTrace adapter
│       │   ├── maf.py               # Microsoft Agent Framework GA 1.0 → AgentTrace adapter
│       │   └── autogen.py           # AutoGen (legacy) → AgentTrace adapter
│       └── judge/
│           ├── __init__.py
│           └── llm_judge.py   # LiteLLM judge logic
├── tests/
│   ├── sample_traces/
│   │   ├── good_trace.json           # AgentTrace schema — good agent
│   │   ├── bad_trace.json            # AgentTrace schema — bad agent
│   │   ├── inefficient_trace.json    # AgentTrace schema — inefficient agent
│   │   ├── langchain_raw.json        # Raw LangChain trace (adapter input fixture)
│   │   ├── openai_agents_raw.json    # Raw OpenAI Agents SDK trace (adapter input fixture)
│   │   ├── maf_raw.json              # Placeholder — MAF adapter is a stub, kept for structure
│   │   └── autogen_raw.json          # Raw AutoGen legacy trace (adapter input fixture)
│   ├── test_efficiency_score.py      # Deterministic tool tests — no API key needed
│   ├── test_adapters.py              # Adapter tests — no API key needed
│   ├── test_error_contract.py        # Error shape validation — no API key needed
│   └── test_server.py               # Server import and registration tests
├── pyproject.toml
├── README.md
└── .env.example
```

**Important — this MCP is framework-agnostic.** The adapters are optional convenience helpers. The core tools (`judge_trace`, `trace_breakdown`, `efficiency_score`) accept any valid `AgentTrace` JSON regardless of which framework produced it. Do not position this as a MAF-specific tool.

---

## Trace Input Schema (Pydantic)

The MCP tools accept a trace as a JSON string. Define this schema in `models/trace.py`:

```python
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
```

**Important:** All fields except `steps` are optional — zero instrumentation means we work with whatever the user can provide.

---

## MCP Tools to Build

### Tool 1: `judge_trace`

**Description:** Diagnoses an agent execution trace — identifies root causes of failure, scores performance across four dimensions, and returns a concrete fix.

**Input:**
```json
{
  "trace": "<JSON string of AgentTrace>",
  "goal": "optional override — what was the agent supposed to do?"
}
```

**Output:**
```json
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
  "summary": "Agent completed the goal with minor inefficiencies...",
  "root_causes": [
    "Unnecessary second search call caused token inflation — result was already available from step 1",
    "Agent did not use tool output before proceeding to next step"
  ],
  "strengths": ["Clear reasoning steps", "Correct tool selection"],
  "weaknesses": ["Redundant tool call on step 4", "Verbose output"],
  "recommendation": "Remove duplicate search call — saves ~400 tokens",
  "explain_like_im_5": "The agent searched the internet twice for the same thing when it only needed to do it once, which wasted time and money.",
  "confidence": "high"
}
```

**`verdict` values:** `"production-ready"` | `"needs optimisation"` | `"broken"`
- `production-ready` = overall_score ≥ 0.85
- `needs optimisation` = overall_score 0.6–0.84
- `broken` = overall_score < 0.6

**Grade mapping — simple A/B/C/D/F only, no +/- variants:**
- 0.9+ = A
- 0.8-0.89 = B
- 0.7-0.79 = C
- 0.6-0.69 = D
- below 0.6 = F

**Judge prompt design for `judge_trace` (implement exactly as below):**

```python
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
```

---

### Tool 2: `trace_breakdown`

**Description:** Step-by-step scoring of every decision the agent made.

**Input:**
```json
{
  "trace": "<JSON string of AgentTrace>"
}
```

**Output:**
```json
{
  "steps": [
    {
      "step_number": 1,
      "description": "Agent called search tool",
      "score": 0.9,
      "assessment": "Correct tool, good query formulation",
      "flag": null
    },
    {
      "step_number": 4,
      "description": "Agent called search tool again",
      "score": 0.3,
      "assessment": "Redundant — same query as step 1",
      "flag": "REDUNDANT_TOOL_CALL"
    }
  ],
  "flags_summary": ["REDUNDANT_TOOL_CALL"],
  "worst_step": 4,
  "best_step": 1
}
```

**Flag types to detect:**
- `REDUNDANT_TOOL_CALL` — same tool called with same/similar input
- `HALLUCINATED_TOOL` — tool call references a tool not in the trace
- `REASONING_GAP` — assistant response doesn't follow from previous tool output
- `GOAL_DRIFT` — agent appears to deviate from original goal
- `PREMATURE_STOP` — agent stopped before completing the goal

**Prompt design for `trace_breakdown` (implement exactly as below):**

```python
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
```

---

### Tool 3: `efficiency_score`

**Description:** Pure deterministic efficiency analysis — token usage, tool redundancy, latency. No LLM call, no API key needed, runs instantly.

**Implementation note:** This is the only sync-safe tool but must still be declared `async` to be consistent with the MCP server's async context. Use `asyncio.to_thread` is NOT needed — just declare `async def` and compute synchronously inside. No blocking I/O occurs.

**Input:**
```json
{
  "trace": "<JSON string of AgentTrace>"
}
```

**Output:**
```json
{
  "token_efficiency": {
    "total_tokens": 4820,
    "tokens_per_step": 482,
    "rating": "moderate",
    "advice": "Consider compressing tool outputs before passing to next step"
  },
  "tool_efficiency": {
    "total_tool_calls": 6,
    "redundant_calls": 1,
    "failed_calls": 0,
    "redundancy_rate": 0.17,
    "rating": "good"
  },
  "latency": {
    "total_ms": 8400,
    "slowest_step": 3,
    "slowest_tool": "web_search",
    "rating": "acceptable"
  },
  "overall_efficiency_score": 0.74
}
```

**Deliberately excluded from v1:** `estimated_cost_usd` — requires hardcoded per-model pricing that breaks whenever providers change rates. Omit entirely in v1. Add in v2 with a maintained pricing lookup table.

**Deterministic rating thresholds and numeric mapping (hardcode exactly):**

```python
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

# Thresholds
def rate_tokens_per_step(tps: float) -> str:
    if tps < 300: return "good"
    if tps <= 600: return "moderate"
    return "high"

def rate_redundancy(rate: float) -> str:
    if rate < 0.1: return "good"
    if rate <= 0.25: return "moderate"
    return "poor"

def rate_latency(ms: float) -> str:
    if ms < 5000: return "fast"
    if ms <= 15000: return "acceptable"
    return "slow"

def compute_overall_efficiency(token_rating: str, tool_rating: str, latency_rating: str) -> float:
    # Weighted average: tokens 40%, tools 40%, latency 20%
    token_score = RATING_SCORES.get(token_rating, 0.5)
    tool_score = RATING_SCORES.get(tool_rating, 0.5)
    latency_score = RATING_SCORES.get(latency_rating, 0.5)
    return round((token_score * 0.4) + (tool_score * 0.4) + (latency_score * 0.2), 2)
```

If `total_latency_ms` or `token_count` fields are missing from the trace, default their ratings to `"acceptable"` (score 0.6) rather than failing.

**Redundancy detection logic (implement exactly):**
```python
def detect_redundant_calls(steps: list[TraceStep]) -> int:
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
```

**`failed_calls` definition:** Count of steps where `step.tool_call is not None and step.tool_call.error is not None`. Any tool call with a non-null error field is a failed call.

**`tokens_per_step` priority chain — implement exactly in this order:**
```python
def compute_tokens(trace: AgentTrace) -> tuple[int | None, float | None]:
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
```
If both are missing → set `tokens_per_step = null` and token rating = `"acceptable"` (score 0.6).

**Null latency handling:** If no `tool_call.latency_ms` values are present across any step, set `slowest_step = null`, `slowest_tool = null`, `total_ms = null`, and latency rating = `"acceptable"` (score 0.6). Never raise on missing latency data.

---

## LiteLLM Judge Setup (`judge/llm_judge.py`)

```python
import litellm
import json
import re
import os

OPENAI_MODELS = ["gpt-", "azure/gpt-"]

def _supports_json_mode(model: str) -> bool:
    """Only OpenAI/Azure OpenAI models support response_format json_object natively."""
    return any(model.startswith(prefix) for prefix in OPENAI_MODELS)

def _extract_json(text: str) -> dict:
    """Fallback JSON extractor for models that don't support json_object mode.
    Strips markdown code fences and extracts first valid JSON object."""
    # Strip ```json ... ``` fences
    text = re.sub(r"```json\s*|\s*```", "", text).strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON found in model response: {text[:200]}")

async def call_judge(system_prompt: str, user_content: str) -> dict:
    model = os.getenv("JUDGE_MODEL", "azure/claude-opus-4-6")
    
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt + "\n\nYou MUST respond with valid JSON only. No explanation, no markdown, no preamble."},
            {"role": "user", "content": user_content}
        ],
        temperature=0.1
    )
    
    # Only add response_format for models that support it natively
    if _supports_json_mode(model):
        kwargs["response_format"] = {"type": "json_object"}
    
    response = await litellm.acompletion(**kwargs)
    raw = response.choices[0].message.content
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _extract_json(raw)
```

**Supported models via env var `JUDGE_MODEL`:**
- `azure/claude-opus-4-6` (default — best quality judge, ranked #1 on Azure leaderboard)
- `azure/gpt-4.1` (fast alternative if Opus not deployed)
- `azure/gpt-4o` (fallback for older Azure deployments)
- `gpt-4o-mini` (for open source users without Azure)
- Any LiteLLM-supported model string

**Switching models requires only a `.env` file change — zero code change:**
```env
# Primary (default) — Azure OpenAI with Claude Opus 4-6
JUDGE_MODEL=azure/claude-opus-4-6
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Alternative — Azure OpenAI with GPT-4.1
JUDGE_MODEL=azure/gpt-4.1

# For open source users without Azure
JUDGE_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# For Anthropic direct
JUDGE_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```

**Why claude-opus-4-6 as default:** Ranked #1 on Azure AI Foundry model leaderboard for quality. For a judge evaluating nuanced agent reasoning — goal drift, reasoning gaps, tool redundancy — quality of evaluation matters most. Switching to a cheaper model is always one env var change away.

---

## Error Response Contract (Gap 3)

All three tools MUST return errors in this exact shape — never raise raw exceptions to the MCP client:

```json
{
  "error": true,
  "error_code": "INVALID_TRACE",
  "error_message": "Human readable explanation of what went wrong",
  "detail": "Optional technical detail for debugging"
}
```

**Error codes to implement:**
- `INVALID_TRACE` — trace JSON failed Pydantic validation (missing required `steps` field, wrong types)
- `EMPTY_TRACE` — trace has zero steps
- `JUDGE_FAILED` — LLM call failed or returned unparseable response after fallback extraction
- `PARSE_ERROR` — trace input was not valid JSON at all

**Implementation pattern for every tool:**
```python
async def judge_trace(trace_json: str, goal: str = None) -> str:
    try:
        trace_data = json.loads(trace_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": True, "error_code": "PARSE_ERROR", 
                          "error_message": "Input is not valid JSON", "detail": str(e)})
    if not isinstance(trace_data, dict):
        return json.dumps({"error": True, "error_code": "INVALID_TRACE",
                          "error_message": "Trace must be a JSON object, not an array or primitive"})
    try:
        trace = AgentTrace(**trace_data)
    except ValidationError as e:
        return json.dumps({"error": True, "error_code": "INVALID_TRACE",
                          "error_message": "Trace failed schema validation", "detail": str(e)})
    if not trace.steps:
        return json.dumps({"error": True, "error_code": "EMPTY_TRACE",
                          "error_message": "Trace contains no steps to evaluate"})
    try:
        result = await call_judge(JUDGE_TRACE_SYSTEM, build_judge_prompt(trace, goal))
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": True, "error_code": "JUDGE_FAILED",
                          "error_message": "LLM judge call failed", "detail": str(e)})
```

All tools return `json.dumps(...)` as a string — never raise. MCP clients handle string returns, not exceptions.

---

## MCP Server (`server.py`)

Full implementation — do not leave this as a skeleton. The MCP Python SDK requires explicit `@server.list_tools()` and `@server.call_tool()` handlers. Tool registration is not automatic.

```python
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from dotenv import load_dotenv

from .tools.judge_trace import judge_trace
from .tools.trace_breakdown import trace_breakdown
from .tools.efficiency_score import efficiency_score

load_dotenv()

server = Server("agent-trace-intelligence")

# --- Tool definitions (what the MCP client sees) ---

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="judge_trace",
            description="Diagnoses an agent trace — identifies root causes of failure, scores performance across four dimensions, and suggests a concrete fix. Returns verdict, grade, and plain-English explanation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {
                        "type": "string",
                        "description": "Agent trace as a JSON string conforming to AgentTrace schema"
                    },
                    "goal": {
                        "type": "string",
                        "description": "Optional: override the goal stated in the trace"
                    }
                },
                "required": ["trace"]
            }
        ),
        types.Tool(
            name="trace_breakdown",
            description="Step-by-step scoring of every agent decision. Flags issues like redundant tool calls, reasoning gaps, and goal drift.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {
                        "type": "string",
                        "description": "Agent trace as a JSON string conforming to AgentTrace schema"
                    }
                },
                "required": ["trace"]
            }
        ),
        types.Tool(
            name="efficiency_score",
            description="Deterministic efficiency analysis of token usage, tool redundancy, and latency. No API key required — runs instantly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {
                        "type": "string",
                        "description": "Agent trace as a JSON string conforming to AgentTrace schema"
                    }
                },
                "required": ["trace"]
            }
        ),
    ]

# --- Tool dispatch ---

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "judge_trace":
        result = await judge_trace(
            trace_json=arguments["trace"],
            goal=arguments.get("goal")
        )
    elif name == "trace_breakdown":
        result = await trace_breakdown(trace_json=arguments["trace"])
    elif name == "efficiency_score":
        result = await efficiency_score(trace_json=arguments["trace"])
    else:
        result = json.dumps({"error": True, "error_code": "UNKNOWN_TOOL",
                             "error_message": f"Unknown tool: {name}"})

    return [types.TextContent(type="text", text=result)]

# --- Entrypoint ---

async def _main():
    async with stdio_server() as streams:
        await server.run(*streams)

def main():
    """Sync entrypoint required by pyproject.toml scripts."""
    asyncio.run(_main())
```

**Note on entrypoint:** `pyproject.toml` scripts must point to a sync function. `main()` is the sync wrapper that calls `asyncio.run()`. The script entry is `agent_trace_intelligence.server:main` (sync), NOT `_main` (async).

---

## Environment Variables (`.env.example`)

```env
# ⚠️  DEFAULT MODEL REQUIRES AZURE CREDENTIALS
# The default JUDGE_MODEL=azure/claude-opus-4-6 requires Azure OpenAI setup below.
# If you don't have Azure, skip to the "No Azure?" section at the bottom.

# Azure OpenAI — primary setup
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Judge model — must match your Azure deployment name exactly (case sensitive)
# Find deployment names in Azure AI Foundry portal → Models + Endpoints
JUDGE_MODEL=azure/claude-opus-4-6

# ---
# No Azure? Use OpenAI instead:
# JUDGE_MODEL=gpt-4o-mini
# OPENAI_API_KEY=sk-...

# Or Anthropic:
# JUDGE_MODEL=claude-haiku-4-5-20251001
# ANTHROPIC_API_KEY=sk-ant-...
```

---

## `pyproject.toml`

```toml
[project]
name = "agent-trace-intelligence"
version = "0.1.0"
description = "MCP server that diagnoses why your agent behaved the way it did — and how to fix it"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "litellm>=1.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0"
]

[project.scripts]
agent-trace-intelligence = "agent_trace_intelligence.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Sample Traces for Testing

Create these in `tests/sample_traces/` so Claude Code can test immediately.

### `good_trace.json`
A 4-step trace where agent correctly searches, finds answer, returns clean output. All tool calls are unique and purposeful.

### `bad_trace.json`
A 6-step trace where agent calls the same search tool twice with identical queries, then returns an incomplete answer that doesn't match the goal.

### `inefficient_trace.json`
A trace with high token counts per step, slow latency values, and redundant tool calls — designed to score low on `efficiency_score` but acceptable on `judge_trace`.

---

## Client Configuration

### Mode 1: Local Developer (stdio) — Claude Desktop / Cursor

Default mode. Runs on the developer's machine. No hosting needed.

```json
{
  "mcpServers": {
    "agent-trace-intelligence": {
      "command": "uv",
      "args": ["run", "agent-trace-intelligence"],
      "env": {
        "AZURE_OPENAI_API_KEY": "your-azure-key",
        "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
        "AZURE_OPENAI_API_VERSION": "2024-08-01-preview",
        "JUDGE_MODEL": "azure/claude-opus-4-6"
      }
    }
  }
}
```

Works with: Claude Desktop, Cursor, VS Code (Copilot MCP), any stdio MCP client.

---

### Mode 2: Enterprise Internal MCP Client (SSE / Streamable HTTP) — V2 ONLY

**Defer SSE to v2.** Implementing SSE transport correctly (uvicorn, starlette, session management, auth middleware) is a significant chunk of work that would block shipping v1. Build and validate stdio first.

For reference when v2 is ready:

**Server changes needed:**
- Add `--transport sse` flag to server startup
- Server binds to `0.0.0.0:8000` and exposes `/sse` endpoint
- Add `uvicorn` or `starlette` as dependency for HTTP transport

**Hosting options (cheapest to most robust):**
- Azure Container Apps — recommended, scales to zero, ~$0 at low usage
- Azure App Service (B1 tier) — ~$13/month, always on
- Azure Functions (custom handler) — serverless, pay per call

**Enterprise client config (SSE):**
```json
{
  "mcpServers": {
    "agent-trace-intelligence": {
      "url": "https://your-container-app.azurecontainerapps.io/sse",
      "transport": "sse"
    }
  }
}
```

**Enterprise considerations to implement:**
- Add `API_KEY` env var for simple bearer token auth — validate in a middleware wrapper around the MCP server
- Log all tool calls to Azure Monitor / Application Insights via OpenTelemetry (optional but enterprise-friendly)
- Use Azure Key Vault reference for the judge LLM API key instead of plain env var
- Deploy via GitHub Actions CI/CD — include a `Dockerfile` and `container-app.yaml` in the repo

**Infrastructure note:** The judge LLM key (OpenAI/Azure OpenAI/Anthropic) lives server-side — individual enterprise users never need their own key. This is a meaningful advantage for internal enterprise deployment: one key, governed centrally, all agents share the eval endpoint.

**Not tied to Azure:** The SSE server itself is just a Python HTTP server. It can run on any cloud or on-prem VM.

---

## Format Adapters (`formats/`)

**Why this exists:** Most agent frameworks don't emit `AgentTrace`-shaped JSON natively. Without adapters, "zero instrumentation" is only true if the user's trace already matches the schema — which it won't. Adapters turn this weakness into a feature.

Each adapter is a simple pure function: `def adapt(raw: dict) -> AgentTrace`.

**Error handling requirement — mandatory for all adapters:** Each adapter MUST raise `ValueError` with a descriptive message if required fields are missing or the input shape is unrecognisable. Explicit failure beats silent wrong output. Example:
```python
if "runs" not in raw:
    raise ValueError("Input does not look like a LangChain trace — expected 'runs' key at top level")
```

### `formats/langchain.py`
Convert LangChain callback handler output or LangSmith trace export to `AgentTrace`.
Key mappings:
- LangChain `on_tool_start` / `on_tool_end` events → `TraceStep` with `ToolCall`
- `on_llm_start` / `on_llm_end` → `TraceStep` with role = "assistant"
- `on_chain_start` input → `AgentTrace.goal`

### `formats/openai_agents.py`
Convert OpenAI Agents SDK trace output to `AgentTrace`.
Key mappings:
- `RunStep` objects with `tool_calls` → `TraceStep` with `ToolCall`
- `usage.total_tokens` → `AgentTrace.total_tokens`
- `instructions` → `AgentTrace.goal`

### `formats/maf.py` — Microsoft Agent Framework GA 1.0 (Skeleton)
MAF (`pip install agent-framework`) GA 1.0 released April 3rd 2026. Claude Code has no training data on its trace output format — field names and event structure are unknown until real MAF traces are available.

**Implement as an explicit stub — do NOT invent field names:**
```python
def adapt(raw: dict) -> AgentTrace:
    """
    MAF GA 1.0 adapter — stub pending real trace format confirmation.
    Replace this implementation once a real MAF trace is available.
    See: https://github.com/harinarayn/agent-trace-intelligence/issues (track here)
    """
    raise NotImplementedError(
        "MAF adapter is not yet implemented. "
        "MAF GA 1.0 released April 2026 — real trace format not yet confirmed. "
        "Pass your trace directly as AgentTrace JSON instead, or contribute "
        "the MAF mapping at https://github.com/harinarayn/agent-trace-intelligence"
    )
```
This is intentionally honest — a stub that fails clearly beats a stub that silently maps wrong fields. Will be replaced with real mappings in v1.1 once MAF trace examples are available post-build.

### `formats/autogen.py` — AutoGen (Legacy)
Convert AutoGen (`pip install pyautogen`) message history to `AgentTrace`. AutoGen has a massive existing user base actively building agents today — these are the people most likely to have real traces to feed the judge right now.
Key mappings:
- AutoGen message history list → `TraceStep` list
- `config_list[0]["model"]` → `AgentTrace.model`
- First human message content → `AgentTrace.goal`

### `formats/__init__.py`
Export all adapt functions for clean imports:
```python
from .langchain import adapt as adapt_langchain
from .openai_agents import adapt as adapt_openai_agents
from .maf import adapt as adapt_maf
from .autogen import adapt as adapt_autogen
```

**Build note for Claude Code:** Implement adapters as best-effort — use real framework output shapes but don't import the frameworks as dependencies. Adapters work on raw dicts only. Add to `pyproject.toml` as optional extras, not core dependencies.

**MAF Integration Direction (v1.1):**
- Native support for MAF GA 1.0 execution traces once real trace format is confirmed
- Pre-built evaluation rubrics aligned with MAF agent lifecycle events
- Recommended pairing: use this MCP alongside MAF for enterprise agent debugging

Note: the core MCP remains framework-agnostic. MAF support is an adapter, not a dependency.

---

## README Structure

1. **One-liner:** "Diagnose why your agent did what it did — and how to fix it."
2. **The problem:** 2 sentences — agents are black boxes when they fail, existing tools tell you *what* happened but not *why*
3. **The solution:** 3 tools, zero setup, works in Cursor/Claude Desktop. Not an observability platform — a debugging companion. Complementary to LangSmith/Phoenix — run alongside your existing stack when you need to understand a specific failure.
4. **Install:** `pip install agent-trace-intelligence` or uv
5. **Quick start:** Paste the Claude Desktop config
6. **Tools reference:** Table of 3 tools with inputs/outputs
7. **Sample trace:** Show a real example with full output — including `root_causes` and `explain_like_im_5`
8. **Format adapters:** LangChain, OpenAI Agents, MAF GA 1.0 (v1.1), AutoGen — one-line conversion. Clearly note these are optional helpers — the tools accept any JSON trace from any framework.
9. **Model support + cost guidance:** List supported providers. Note: for CI/CD use set `JUDGE_MODEL=gpt-4o-mini` to keep costs under $0.01 per trace. For interactive debugging, `azure/claude-opus-4-6` gives the best root cause reasoning.
10. **Future direction:** Pattern detection across multiple traces, recurring failure mode detection, enterprise governance signals — planned for v2.
11. **Positioning note:** "This is a debugging tool, not an eval platform. Use it when your agent does something unexpected and you need to understand why."

---

## Build Order for Claude Code

**Important:** Follow this order strictly. Pydantic schema must exist before any tool imports it. Deterministic tool first (no LLM dependency) to validate the schema works. LLM tools after. Avoids circular dependency and import errors.

1. Set up project structure with `uv init`
2. Build `models/trace.py` — Pydantic schema first, everything depends on this
3. Build `judge/llm_judge.py` — LiteLLM wrapper with JSON fallback extractor
4. Build `efficiency_score.py` — deterministic, no LLM, validate schema works here
5. Build `judge_trace.py` — core tool, uses LLM judge
6. Build `trace_breakdown.py` — step scorer, uses LLM judge
7. Build `formats/langchain.py`, `formats/openai_agents.py`, `formats/maf.py`, `formats/autogen.py` — four adapters, no external deps
8. Build `formats/__init__.py` — export all four adapt functions
9. Wire all tools into `server.py` using full registration pattern above — not a skeleton
10. Create 3 AgentTrace sample traces + 4 raw adapter fixtures in `tests/sample_traces/` (maf_raw.json is a placeholder — the adapter is a stub)
11. Run end-to-end test with each sample trace before moving on
12. Write README last

---

## Recommended Model for Development and Testing

**Use `azure/claude-opus-4-6` deployed via Azure AI Foundry.**

Reasons:
- Ranked #1 on Azure AI Foundry model leaderboard for quality
- Best reasoning for nuanced trace evaluation — detects goal drift, reasoning gaps, subtle tool misuse that cheaper models miss
- Already available in Azure — deploy from Foundry model catalog, no separate API key needed
- Switching to a faster/cheaper model later is one `.env` line change — no code change

**For open source users** (who may not have Azure), the README should note `gpt-4o-mini` as the fallback default — universally accessible and cheap. For CI/CD batch use, recommend `gpt-4o-mini` explicitly to keep costs under $0.01 per trace.

**Deployment name:** Set `JUDGE_MODEL` to exactly match your Azure deployment name (case sensitive). Find it in Azure AI Foundry portal under Models + Endpoints.

---

## Success Criteria

- [ ] All 3 tools callable from Claude Desktop via MCP
- [ ] Works with OpenAI, Azure OpenAI, and Anthropic keys via env var only
- [ ] `efficiency_score` runs with no API key (deterministic)
- [ ] `efficiency_score` handles missing token and latency data gracefully — nulls not crashes
- [ ] `tokens_per_step` follows priority chain: AgentTrace.total_tokens → sum TraceStep.token_count → null
- [ ] `failed_calls` = count of steps where tool_call.error is not None
- [ ] `slowest_step` and `slowest_tool` return null when no latency data present
- [ ] Handles malformed/incomplete traces gracefully with defined error codes
- [ ] `judge_trace` output includes `root_causes`, `verdict`, `explain_like_im_5` on every call
- [ ] `verdict` is one of exactly: "production-ready", "needs optimisation", "broken"
- [ ] `root_causes` is an empty list (not null) when agent performed well
- [ ] `explain_like_im_5` is plain English with no technical jargon
- [ ] README has copy-paste Claude Desktop config that works first try
- [ ] Sample traces produce meaningfully different scores, verdicts, and root causes from each other
- [ ] All 4 format adapters (LangChain, OpenAI Agents, MAF GA 1.0, AutoGen legacy) work without importing framework deps
- [ ] MAF adapter raises `NotImplementedError` with clear message — stub, not broken
- [ ] All other adapters raise `ValueError` with descriptive message on unrecognisable input
- [ ] README makes clear this MCP is a debugging tool, not an observability platform
- [ ] README includes CI/CD cost guidance (`gpt-4o-mini` for batch use)

---

## Claude Project Structure

Based on the pattern established in `adf-cost-intelligence-mcp`. Create this structure at project root.

### `.claude/settings.json`
```json
{
  "model": "claude-sonnet-4-6",
  "context": {
    "include": ["CLAUDE.md", "docs/architecture.md"]
  }
}
```

### `.claude/skills/judge-trace/SKILL.md`
```markdown
# Skill: Judge Agent Trace

## Purpose
Evaluate an agent execution trace for quality, reasoning, and goal completion.

## When to Use
- "diagnose this trace"
- "debug this agent run"
- "why did my agent fail?"
- "what went wrong in this trace?"
- "judge this trace"
- "evaluate this trace"
- "how did my agent do?"

## Prompt Template
Use the `judge_trace` tool with the trace JSON provided by the user.

After receiving results:
1. Lead with the verdict and grade — e.g. "needs optimisation (B)"
2. Surface root_causes first — this is the core diagnostic value
3. Summarise strengths and weaknesses in 2-3 bullet points each
4. End with the recommendation and explain_like_im_5 if the user is non-technical
5. Suggest running `trace_breakdown` if the user wants step-level detail

## Expected Output Shape
```json
{
  "overall_score": 0.82,
  "grade": "B",
  "verdict": "needs optimisation",
  "dimension_scores": { "goal_completion": 0.9, "reasoning_clarity": 0.8, "tool_usage": 0.75, "output_quality": 0.83 },
  "summary": "...",
  "root_causes": ["specific causal explanation referencing step/tool"],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "recommendation": "...",
  "explain_like_im_5": "Plain English sentence for non-technical readers",
  "confidence": "high"
}
```

## Follow-Up Actions
- User wants step detail → invoke `trace_breakdown`
- User wants token/latency analysis → invoke `efficiency_score`
```

### `.claude/skills/efficiency-check/SKILL.md`
```markdown
# Skill: Efficiency Check

## Purpose
Run a free, instant deterministic efficiency analysis on an agent trace — no API key needed.

## When to Use
- "how efficient was my agent?"
- "check token usage"
- "was there any redundancy?"
- "how slow was this trace?"
- "quick efficiency check"

## Prompt Template
Use the `efficiency_score` tool with the trace JSON provided by the user.

After receiving results:
1. Report the overall_efficiency_score with a plain-English rating
2. Flag any redundant tool calls with count
3. Call out the slowest tool if latency data is present
4. Give the token advice verbatim if rating is "moderate" or "high"

## Expected Output Shape
```json
{
  "token_efficiency": { "total_tokens": 4820, "tokens_per_step": 482, "rating": "moderate", "advice": "..." },
  "tool_efficiency": { "total_tool_calls": 6, "redundant_calls": 1, "failed_calls": 0, "redundancy_rate": 0.17, "rating": "good" },
  "latency": { "total_ms": 8400, "slowest_step": 3, "slowest_tool": "web_search", "rating": "acceptable" },
  "overall_efficiency_score": 0.74
}
```

## Follow-Up Actions
- User wants quality score → invoke `judge_trace`
- User wants step-level breakdown → invoke `trace_breakdown`
```

### `CLAUDE.md` (project root)
Create a `CLAUDE.md` at project root with:
- One-liner on what this project is
- Build order reference (point to spec)
- Key invariants: all tools return JSON strings never raise, error contract shape, efficiency_score is always deterministic
- Note on MAF adapter status (stub, intentional)
- How to run tests: `python -m pytest tests/ -v`

---

## Git Strategy

Based on the pattern used in `adf-cost-intelligence-mcp`. Single clean release commit for v1.0.0, then ongoing work on `develop`.

### Branch Strategy
- `main` — production-ready only. Protected. Never commit directly during build.
- `develop` — active build work. All build commits go here.
- PR from `develop` → `main` for each release.

### Commit convention during build
Use conventional commits:
```
feat: add efficiency_score tool with deterministic rating logic
feat: add judge_trace tool with LiteLLM judge
feat: add trace_breakdown tool with flag detection
feat: add LangChain and OpenAI Agents format adapters
test: add sample traces and end-to-end test suite
docs: add README, architecture, CHANGELOG
```

### Release commit (v1.0.0)
When everything passes all tests and manual checks, squash into one clean commit on `main`:
```
Initial release: Agent Trace Intelligence MCP v1.0.0
```
This matches the adf-cost-intelligence-mcp pattern — clean public history.

### Required repo files (match adf-cost-intelligence-mcp exactly)
- `LICENSE` — MIT
- `CONTRIBUTING.md` — fork, branch from main, run tests, open PR
- `SECURITY.md` — note that traces are processed locally, LLM judge key lives server-side, `.env` never committed
- `CHANGELOG.md` — Keep a Changelog format, semver
- `docs/architecture.md` — Mermaid diagram of the system (MCP client → server → tools → judge/engine)
- `.gitignore` — include `.env`, `.claude/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `dist/`

### `.gitignore`
```gitignore
# Credentials — NEVER commit
.env
*.env.local

# Python
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.eggs/

# Virtual environments
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Claude Code session data — local only
.claude/

# Logs
*.log
```

### GitHub Actions CI (`.github/workflows/ci.yml`)
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: python -m pytest tests/ -v --tb=short

      - name: Verify server imports cleanly
        run: python -c "from agent_trace_intelligence.server import server; print('Server import OK')"
```

Note: CI does NOT run `judge_trace` or `trace_breakdown` — those make live LLM calls. Only `efficiency_score` and error-path tests run in CI. LLM tool tests are manual pre-publish only.

### `pyproject.toml` dev dependencies
Add a `[dev]` optional group for test deps:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0"
]
```

### Git skill for release
Add `.claude/skills/git-release/SKILL.md` to the project:
```markdown
# Skill: Git Release

## Purpose
Prepare and push a clean release commit to main.

## When to Use
- "release v1.0.0"
- "push to main"
- "create the release commit"

## Prompt Template
1. Run `python -m pytest tests/ -v` — confirm all tests pass
2. Update CHANGELOG.md with release date and version
3. Bump version in pyproject.toml
4. Stage all changes: `git add -A`
5. Commit: `git commit -m "Initial release: Agent Trace Intelligence MCP v{version}"`
6. Tag: `git tag v{version}`
7. Push: `git push origin main --tags`

## Guardrails
- NEVER push if any test fails
- NEVER push to main directly during active development — only on release
- Always confirm CHANGELOG is updated before committing
```

---

## Test Plan

### Scripted Tests (automated — `python -m pytest tests/ -v`)

**`test_efficiency_score.py`** — no API key needed, all run in CI:
```
test_good_trace_scores_high          # overall_efficiency_score > 0.8
test_bad_trace_scores_low            # redundancy detected, score < 0.6
test_inefficient_trace_scores_low    # high tokens_per_step → "high" rating
test_missing_token_data_returns_null # tokens_per_step = null, no crash
test_missing_latency_returns_null    # slowest_step = null, no crash
test_redundant_calls_detected        # detect_redundant_calls returns > 0
test_failed_calls_counted            # tool_call.error != None increments failed_calls
test_empty_trace_returns_error       # EMPTY_TRACE error code
test_invalid_json_returns_error      # PARSE_ERROR error code
test_json_array_returns_error        # INVALID_TRACE — not a dict
test_missing_steps_returns_error     # INVALID_TRACE — steps field missing
```

**`test_adapters.py`** — no API key needed, runs in CI:
```
test_langchain_adapt_valid_input     # returns AgentTrace, no exception
test_langchain_adapt_bad_input       # raises ValueError with descriptive message
test_openai_agents_adapt_valid       # returns AgentTrace, no exception
test_openai_agents_adapt_bad_input   # raises ValueError with descriptive message
test_autogen_adapt_valid_input       # returns AgentTrace, no exception
test_autogen_adapt_bad_input         # raises ValueError with descriptive message
test_maf_raises_not_implemented      # NotImplementedError — stub confirmed
```

**`test_error_contract.py`** — validates all error response shapes:
```
test_all_tools_return_string         # never raises, always returns json string
test_error_shape_has_required_keys   # error, error_code, error_message always present
test_parse_error_on_invalid_json
test_invalid_trace_on_bad_schema
test_empty_trace_on_zero_steps
```

**`test_server.py`** — server import and registration:
```
test_server_imports_cleanly          # no ImportError
test_list_tools_returns_three        # exactly 3 tools registered
test_tool_names_correct              # judge_trace, trace_breakdown, efficiency_score
test_unknown_tool_returns_error      # UNKNOWN_TOOL error code
```

### Manual Tests (before publishing to GitHub)

Run these locally with a real API key. Not in CI.

**1. End-to-end `efficiency_score` (no API key)**
```bash
# Start server via MCP Inspector
npx @modelcontextprotocol/inspector uv run agent-trace-intelligence

# Call efficiency_score with good_trace.json content
# Verify: overall_efficiency_score > 0.8, no null crashes
# Call with inefficient_trace.json
# Verify: different score, redundant_calls > 0
```

**2. End-to-end `judge_trace` (requires JUDGE_MODEL env)**

Run this twice — once with the default Opus, once with mini. Compare outputs before publishing.

```bash
# Pass 1 — primary setup (azure/claude-opus-4-6, the default)
# JUDGE_MODEL=azure/claude-opus-4-6 + AZURE_OPENAI_API_KEY
# Call judge_trace with good_trace.json — expect grade A or B
# Call judge_trace with bad_trace.json — expect grade D or F
# Record: are weaknesses specific or generic? Is recommendation actionable?
# Record: does it catch the redundant tool call on bad_trace without being told?

# Pass 2 — fallback model (gpt-4o-mini + OPENAI_API_KEY)
# Repeat same calls with same traces
# Compare: does Opus catch things mini misses? Is the recommendation more specific?
# This validates the "quality justifies cost" claim in the README
# If outputs are indistinguishable → downgrade the default model recommendation
```

**3. End-to-end `trace_breakdown` (requires JUDGE_MODEL env)**
```bash
# Call trace_breakdown with bad_trace.json
# Verify: REDUNDANT_TOOL_CALL flag appears
# Verify: worst_step matches the redundant step number
# Verify: flags_summary is a list not null
```

**4. Claude Desktop integration**
```bash
# Paste client config from README into claude_desktop_config.json
# Restart Claude Desktop
# Confirm agent-trace-intelligence appears in tool list
# Run: "use efficiency_score on this trace: {paste good_trace.json content}"
# Confirm response is structured and readable
```

**5. Error handling (manual spot-check)**
```bash
# Pass empty string → expect PARSE_ERROR
# Pass [] (JSON array) → expect INVALID_TRACE
# Pass {"steps": []} → expect EMPTY_TRACE
# Pass garbage string → expect PARSE_ERROR
```

**6. Model switching (manual)**
```bash
# Test with JUDGE_MODEL=azure/claude-opus-4-6 (default — must pass)
# Test with JUDGE_MODEL=gpt-4o-mini (OpenAI — confirm json_object mode works)
# Test with JUDGE_MODEL=claude-haiku-4-5-20251001 (Anthropic direct — confirm fallback extractor works)
# For all three: confirm valid JSON returned, grade is A/B/C/D/F, no raw exceptions
# Cross-reference Opus vs mini output from test 2 — document quality delta in post-build checklist
```

---

## Post-Build README Checklist

Things to update in README **after** the build and manual tests are complete. Do not pre-fill these — values must come from real runs.

- [ ] **Real sample output** — replace placeholder output examples with actual `judge_trace` and `efficiency_score` output from running `good_trace.json`
- [ ] **Actual grade examples** — show what grade A looks like vs grade F with real trace content
- [ ] **MAF adapter status note** — add a callout: "MAF adapter is a stub — contribute real MAF trace mappings via PR"
- [ ] **Confirmed model list** — after testing, update supported models table with which ones were actually verified to work (not just theoretically supported via LiteLLM)
- [ ] **Opus vs mini quality delta** — document what Opus caught that mini missed (or didn't). If the outputs are indistinguishable on the sample traces, revisit whether Opus should remain the default or whether the README recommendation should be softened
- [ ] **MCP Inspector screenshot** — add `docs/images/mcp-inspector.png` showing the 3 tools registered (match adf-cost-intelligence-mcp pattern)
- [ ] **Cost per trace estimates** — after running real judge calls, document approximate cost per trace for gpt-4o-mini vs claude-opus-4-6
- [ ] **Known limitations** — document anything discovered during build: max trace size, token limits, any edge cases found in testing
- [ ] **Version badge** — add `![Version](https://img.shields.io/badge/version-0.1.0-blue)` to README header after confirming pypi publish works
- [ ] **MAF adapter tracking issue** — open a GitHub issue for "Implement MAF GA 1.0 adapter" immediately after publish, link it from README and from `formats/maf.py` stub comment
