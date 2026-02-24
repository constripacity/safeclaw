# Security Model — SafeClaw

## Philosophy

SafeClaw is built on the principle that **AI agents should never have more access than explicitly granted**. Unlike typical autonomous agents (OpenClaw, PicoClaw, etc.), SafeClaw enforces:

1. **Deny by default** — nothing is allowed unless policy.yaml says so
2. **LLM suggests, policy decides** — the AI can propose actions, but execution requires policy approval
3. **Full audit trail** — every action is logged with automatic secret redaction
4. **Path confinement** — all operations restricted to `project_root`

## Threat Model

| Threat | Description | Mitigation | Status |
|--------|-------------|------------|--------|
| **Prompt Injection** | Malicious instructions hidden in scanned files trick the LLM planner | LLM can only output JSON plans validated against policy; no direct execution | ✅ Mitigated |
| **Privilege Escalation** | Plugin attempts to access files outside project root | Path enforcement: all targets validated with `path.relative_to(root)` | ✅ Mitigated |
| **Credential Leaks** | API keys or tokens appear in logs | Automatic regex-based redaction in all audit log writes | ✅ Mitigated |
| **Malicious Plugins** | Third-party plugin exfiltrates data | Plugin allowlist in policy.yaml; no dynamic plugin loading from network | ✅ Mitigated |
| **Exposed Interfaces** | Web dashboard reachable from network | Dashboard binds to 127.0.0.1 only; bearer token auth required | ✅ Mitigated |
| **Arbitrary Shell Execution** | Agent runs destructive commands | `allow_shell: false` by default; no shell plugin included | ✅ Mitigated |
| **Resource Exhaustion** | Plugin scans infinite files or huge files | `max_files`, `max_file_mb`, `timeout_seconds` limits in policy | ✅ Mitigated |
| **Supply Chain Attack** | Dependency contains malicious code | Minimal dependencies; `ruff` + CI checks; no auto-install of plugins | ⚠️ Partially mitigated |
| **Planner Prompt Injection** | Malicious content in scanned files influences LLM plan | LLM output is parsed as JSON only; every step validated against policy; max_steps limit | ✅ Mitigated |
| **API Key Exposure** | LLM API keys leak into logs or config | Keys read from env vars (never in policy.yaml); audit redaction catches leaked keys | ✅ Mitigated |
| **Dashboard Token Theft** | Bearer token compromised | Token stored in .safeclaw/ (gitignored); dashboard localhost-only; token shown once at startup | ⚠️ Partially mitigated |

## What SafeClaw Does NOT Protect Against

- Compromise of the host OS itself
- Malicious policy.yaml (if attacker can edit your config, you have bigger problems)
- Side-channel attacks from LLM API providers
- Bugs in Python/OS that bypass path restrictions

## Responsible Disclosure

If you discover a security issue, please open a GitHub issue tagged `security` or contact the maintainer directly. Do not publicly disclose vulnerabilities before a fix is available.

## Comparison: SafeClaw vs. Typical AI Agents

| Feature | Typical Agent (OpenClaw) | SafeClaw |
|---------|--------------------------|----------|
| Shell access | Often enabled by default | Denied by default |
| File access | Full disk | Project root only |
| Network | Usually allowed | Denied by default |
| Plugin system | Open marketplace | Explicit allowlist |
| Audit logging | Optional/none | Mandatory, redacted |
| LLM execution | Direct tool calls | JSON plan → policy validation → execution |
