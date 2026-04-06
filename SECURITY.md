# Security Policy

## Security Design

Agent Trace Intelligence is designed with security in mind:

**Traces are processed locally.** When running in stdio mode (the default), trace data is processed on your machine and never sent to any third party except the LLM judge model you configure. Only `judge_trace` and `trace_breakdown` send data to the LLM. `efficiency_score` is fully local.

**The LLM judge key lives server-side.** In enterprise deployments, the API key never reaches individual users. It is configured once on the server. This is a meaningful advantage for enterprise governance.

**`.env` files must never be committed.** The `.gitignore` excludes `.env` by default. Never commit credentials.

## Sensitive Data in Traces

Be careful about what you include in traces passed to `judge_trace` or `trace_breakdown`. If your agent traces contain PII, secrets, or sensitive business data:
- Use `efficiency_score` only (no LLM call, fully local)
- Redact sensitive fields before passing to LLM tools
- In enterprise deployments, confirm your LLM provider's data retention policy

## Reporting Vulnerabilities

If you discover a security vulnerability, please do NOT open a public GitHub issue.

Email: security@harinarayn.dev (or open a private security advisory on GitHub)

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge within 48 hours and aim to resolve critical issues within 7 days.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
