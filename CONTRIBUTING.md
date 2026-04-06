# Contributing to Agent Trace Intelligence

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a branch from `main` for your change:
   ```bash
   git checkout -b feat/your-feature-name
   ```
4. Install dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
5. Make your changes
6. Run the test suite. All tests must pass:
   ```bash
   python -m pytest tests/test_efficiency_score.py tests/test_adapters.py tests/test_error_contract.py tests/test_server.py -v
   ```
7. Open a Pull Request against `main`

## Priority Contributions

- **MAF GA 1.0 adapter**: If you have access to real MAF trace output, contribute the field mappings in `src/agent_trace_intelligence/formats/maf.py`. See the stub and the issue tracker for details.
- **New format adapters**: CrewAI, Semantic Kernel, Smolagents, etc.
- **Test coverage**: Additional edge cases for efficiency_score and adapter error handling

## Code Standards

- All tools MUST return JSON strings. Never raise exceptions to the MCP client
- Error responses MUST follow the contract: `{"error": true, "error_code": "...", "error_message": "...", "detail": "..."}`
- Adapters MUST raise `ValueError` with a descriptive message on unrecognisable input (except MAF which raises `NotImplementedError`)
- No framework imports in adapters. Work on raw dicts only
- Type hints required for all public functions
- Add/update tests for any new functionality

## Commit Convention

Use conventional commits:
```
feat: add CrewAI format adapter
fix: handle missing latency_ms in efficiency_score
test: add edge case for empty tool_calls list
docs: update README with CrewAI adapter example
```
