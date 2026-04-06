# Agent Trace Intelligence MCP

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![MCP](https://img.shields.io/badge/MCP-stdio-green)
![PyPI](https://img.shields.io/pypi/v/agent-trace-intelligence)
![License MIT](https://img.shields.io/badge/license-MIT-brightgreen)
![CI](https://github.com/harinarayn/agent-trace-intelligence/actions/workflows/ci.yml/badge.svg)

**Diagnose why your agent did what it did, and how to fix it.**

## The Problem

When an AI agent fails or behaves unexpectedly, existing tools tell you *what* happened: token counts, step logs, latency metrics. But they don't tell you *why* the agent made a wrong turn or *how* to fix it. Debugging agents means staring at raw traces and guessing.

## The Solution

Agent traces show you what happened. This tool tells you why it went wrong and what to change. Pass in any agent trace JSON and get root causes, scores, and a concrete fix back. Zero instrumentation required.

Use it alongside LangSmith, Arize Phoenix, and W&B Weave. When your observability stack surfaces a failure, this is where you go to diagnose it.

Works in Cursor, Claude Desktop, VS Code (Copilot MCP), and any stdio MCP client.

---

## How It Fits

This tool explains why a single agent trace behaved the way it did.

It complements existing observability tools:

- **Azure Application Insights, AWS CloudWatch, GCP Cloud Trace**: show what happened across runs
- **LangSmith, Arize Phoenix, W&B Weave**: track agent behaviour over time

This tool answers a narrower question: why did this specific trace fail, and what exactly needs to change?

---

## Install

```bash
# With uv (recommended)
uv add agent-trace-intelligence

# Or pip
pip install agent-trace-intelligence
```

---

## Quick Start: Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-trace-intelligence": {
      "command": "uv",
      "args": ["run", "agent-trace-intelligence"],
      "env": {
        "AZURE_AI_API_KEY": "your-azure-ai-foundry-key",
        "AZURE_AI_API_BASE": "https://your-resource.cognitiveservices.azure.com/",
        "JUDGE_MODEL": "azure_ai/claude-opus-4-6"
      }
    }
  }
}
```

**No Azure?** Use OpenAI instead:
```json
{
  "env": {
    "JUDGE_MODEL": "gpt-4o-mini",
    "OPENAI_API_KEY": "sk-..."
  }
}
```

---

## Tools Reference

| Tool | Description | API Key? | Speed |
|------|-------------|----------|-------|
| `judge_trace` | Root cause analysis, 4-dimension scoring, grade, verdict, plain-English explanation | Required | ~3-5s |
| `trace_breakdown` | Step-by-step scoring with flags (REDUNDANT_TOOL_CALL, REASONING_GAP, etc.) | Required | ~3-5s |
| `efficiency_score` | Deterministic token/latency/redundancy analysis | **Not required** | Instant |

### `judge_trace`

Input:
```json
{
  "trace": "<JSON string of AgentTrace>",
  "goal": "optional: override the goal stated in the trace"
}
```

Output:
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
  "summary": "Agent completed the goal but made one redundant search call",
  "root_causes": [
    "Unnecessary second search call at step 4 caused token inflation. Result was already available from step 2",
    "Agent did not validate tool output before proceeding to the next step"
  ],
  "strengths": ["Clear reasoning steps", "Correct initial tool selection"],
  "weaknesses": ["Redundant tool call on step 4", "Incomplete final output"],
  "recommendation": "Remove duplicate search call at step 4. Saves ~400 tokens",
  "explain_like_im_5": "The agent searched the internet twice for the same thing when it only needed to do it once, which wasted time and money.",
  "confidence": "high"
}
```

**Verdict values:** `"production-ready"` | `"needs optimisation"` | `"broken"`

### `trace_breakdown`

Per-step scoring with flags:
- `REDUNDANT_TOOL_CALL`: same tool called with same/similar input
- `HALLUCINATED_TOOL`: tool referenced that doesn't exist in the trace
- `REASONING_GAP`: response doesn't follow from previous tool output
- `GOAL_DRIFT`: agent deviates from the original goal
- `PREMATURE_STOP`: agent stopped before completing the goal

### `efficiency_score`

No API key required. Deterministic analysis of:
- Token usage (total, per-step, rating: good/moderate/high)
- Tool redundancy (redundant calls, failed calls, redundancy rate)
- Latency (total ms, slowest step/tool, rating: fast/acceptable/slow)
- `overall_efficiency_score` (0.0-1.0 weighted composite)

---

## AgentTrace Schema

All tools accept a trace JSON conforming to this schema:

```json
{
  "trace_id": "optional",
  "agent_name": "optional",
  "goal": "What was the agent trying to do?",
  "model": "gpt-4o",
  "total_tokens": 820,
  "total_latency_ms": 3200,
  "final_output": "The agent's final response",
  "steps": [
    {
      "step_number": 1,
      "role": "user",
      "content": "User message"
    },
    {
      "step_number": 2,
      "role": "assistant",
      "content": "I'll search for that.",
      "token_count": 120
    },
    {
      "step_number": 3,
      "role": "tool",
      "tool_call": {
        "tool_name": "web_search",
        "input": {"query": "..."},
        "output": "Search results...",
        "latency_ms": 1200,
        "error": null
      }
    }
  ]
}
```

All fields except `steps` are optional. Works with whatever you can provide.

---

## Format Adapters

Optional helpers to convert native framework traces to AgentTrace format:

```python
from agent_trace_intelligence.formats import (
    adapt_langchain,      # LangChain callback handler output
    adapt_openai_agents,  # OpenAI Agents SDK RunStep objects
    adapt_autogen,        # AutoGen message history
    adapt_maf,            # MAF GA 1.0 (OpenTelemetry GenAI spans)
)

# Convert and pass directly to any tool
trace = adapt_langchain(raw_langchain_output)
```

These are convenience helpers. The tools accept any valid AgentTrace JSON regardless of framework.

| Adapter | Framework | Status |
|---------|-----------|--------|
| `adapt_langchain` | LangChain callback handler / LangSmith export | v1 |
| `adapt_openai_agents` | OpenAI Agents SDK (RunStep objects) | v1 |
| `adapt_autogen` | AutoGen legacy (`pyautogen`) message history | v1 |
| `adapt_maf` | Microsoft Agent Framework GA 1.0 (OTel spans) | v1 |

---

## Model Support & Cost Guidance

Configure via `JUDGE_MODEL` env var. Zero code change required.

| Use Case | Recommended Model | Cost |
|----------|-------------------|------|
| Best quality (default) | `azure_ai/claude-opus-4-6` | ~$0.015/trace |
| Fast Azure alternative | `azure_ai/gpt-4.1` | ~$0.008/trace |
| Open source / no Azure | `gpt-4o-mini` | ~$0.002/trace |
| CI/CD batch evaluation | `gpt-4o-mini` | < $0.01/trace |
| Anthropic direct | `claude-haiku-4-5-20251001` | ~$0.001/trace |

**For CI/CD use:** Set `JUDGE_MODEL=gpt-4o-mini` to keep costs under $0.01 per trace. For interactive debugging, `azure_ai/claude-opus-4-6` gives the best root cause reasoning.

`efficiency_score` is always free. No model call, no API key.

---

## Future Direction (v2)

- Pattern detection across multiple traces to surface recurring failure modes
- Batch trace analysis for CI/CD quality gates
- Enterprise governance signals to flag traces that violate defined agent policies
- SSE transport for enterprise internal MCP deployment

---

## License

MIT. See [LICENSE](LICENSE)
