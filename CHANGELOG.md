# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-04-06

### Changed
- Rewrote README solution description and removed Positioning Note section

## [0.1.1] - 2026-04-06

### Fixed
- Added README as PyPI long description
- Added package keywords, classifiers, and project URLs

## [0.1.0] - 2026-04-06

### Added
- `judge_trace` MCP tool: LLM-powered root cause analysis with 4-dimension scoring, grade, verdict, root_causes, and explain_like_im_5
- `trace_breakdown` MCP tool: step-by-step scoring with flag detection (REDUNDANT_TOOL_CALL, HALLUCINATED_TOOL, REASONING_GAP, GOAL_DRIFT, PREMATURE_STOP)
- `efficiency_score` MCP tool: deterministic token/latency/redundancy analysis, no API key required
- `AgentTrace` Pydantic v2 schema for framework-agnostic trace input
- LangChain format adapter (`adapt_langchain`): converts callback handler output to AgentTrace
- OpenAI Agents SDK format adapter (`adapt_openai_agents`): converts RunStep objects to AgentTrace
- AutoGen legacy format adapter (`adapt_autogen`): converts message history to AgentTrace
- MAF GA 1.0 adapter stub (`adapt_maf`): raises NotImplementedError pending real trace format confirmation
- Full error contract: all tools return structured JSON errors, never raise
- 7 sample trace fixtures (good, bad, inefficient + 4 raw adapter fixtures)
- 69 automated tests covering efficiency_score, adapters, error contract, and server registration
- stdio MCP transport with full tool registration pattern
- Model-agnostic LLM judge via LiteLLM, supports Azure OpenAI, OpenAI, Anthropic

[Unreleased]: https://github.com/harinarayn/agent-trace-intelligence/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/harinarayn/agent-trace-intelligence/releases/tag/v0.1.0
