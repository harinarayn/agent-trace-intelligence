# CLAUDE.md — Agent Trace Intelligence MCP

## What This Project Is

An MCP server that diagnoses why an AI agent behaved the way it did — and how to fix it. Three tools: `judge_trace` (LLM-powered root cause analysis), `trace_breakdown` (step-by-step flag detection), and `efficiency_score` (deterministic token/latency/redundancy scoring). Zero instrumentation required — just pass a trace JSON.

## Build Order Reference

See `agent_trace_mcp_buildspec.md` for full spec. Build order:
1. models/trace.py — Pydantic schema (everything depends on this)
2. judge/llm_judge.py — LiteLLM wrapper
3. tools/efficiency_score.py — deterministic tool (no LLM)
4. tools/judge_trace.py — LLM tool
5. tools/trace_breakdown.py — LLM tool
6. formats/*.py — four adapters (no framework deps)
7. server.py — full registration pattern
8. tests/ — fixtures and test files

## Key Invariants

**Never raise from tools.** All three tools (`judge_trace`, `trace_breakdown`, `efficiency_score`) MUST return a JSON string — never raise an exception to the MCP client. Error responses use this exact shape:
```json
{"error": true, "error_code": "PARSE_ERROR", "error_message": "...", "detail": "..."}
```
The `error` field is a boolean `true`, not the string `"true"`.

**Error codes:** `PARSE_ERROR`, `EMPTY_TRACE`, `INVALID_TRACE`, `JUDGE_FAILED`, `UNKNOWN_TOOL`

**efficiency_score is always deterministic.** No LLM call, no API key, runs instantly. Safe to run in CI with no credentials.

**MAF adapter is an intentional stub.** `adapt_maf()` raises `NotImplementedError` — this is correct behavior. MAF GA 1.0 released April 2026 and the real trace format is not yet confirmed. Do NOT invent field names.

## Running Tests

```bash
# Run all scripted tests (no API key needed)
python -m pytest tests/test_efficiency_score.py tests/test_adapters.py tests/test_error_contract.py tests/test_server.py -v

# Run all tests
python -m pytest tests/ -v
```

**Do NOT run `judge_trace` or `trace_breakdown` tests in CI** — they make live LLM calls.

## Switching Models

Set `JUDGE_MODEL` env var — zero code change:
```bash
JUDGE_MODEL=gpt-4o-mini          # OpenAI (no Azure)
JUDGE_MODEL=azure/claude-opus-4-6  # Azure (default, best quality)
JUDGE_MODEL=claude-haiku-4-5-20251001  # Anthropic direct
```

## Module Validation Commands

```bash
python -c "from agent_trace_intelligence.models.trace import AgentTrace; print('OK')"
python -c "from agent_trace_intelligence.judge.llm_judge import call_judge; print('OK')"
python -c "from agent_trace_intelligence.tools.efficiency_score import efficiency_score; print('OK')"
python -c "from agent_trace_intelligence.tools.judge_trace import judge_trace; print('OK')"
python -c "from agent_trace_intelligence.tools.trace_breakdown import trace_breakdown; print('OK')"
python -c "from agent_trace_intelligence.formats import adapt_langchain, adapt_openai_agents, adapt_maf, adapt_autogen; print('OK')"
python -c "from agent_trace_intelligence.server import server; print('OK')"
```
