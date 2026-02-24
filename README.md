# SafeClaw

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![CI](https://img.shields.io/github/actions/workflow/status/constripacity/safeclaw/ci.yml?label=CI)

A **sandboxed, policy-driven local dev assistant** that scans your codebase for TODOs, secrets, dependency issues, and more — without ever running arbitrary shell commands or accessing the network.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Scan for TODO/FIXME/HACK markers
safeclaw todo ./my-project/

# Check for hardcoded secrets
safeclaw secrets ./my-project/

# Summarise a build log
safeclaw summarize ./build.log

# Audit dependencies
safeclaw deps ./my-project/

# Repository statistics
safeclaw stats ./my-project/

# View audit log
safeclaw audit

# Show current policy
safeclaw policy
```

## Security Model

SafeClaw is built on the principle that **AI agents should never have more access than explicitly granted**:

- **Deny by default** — no shell access, no network access unless policy.yaml explicitly allows it
- **Path confinement** — all operations are restricted to the declared `project_root`
- **Plugin allowlist** — only explicitly permitted plugins can execute
- **Automatic secret redaction** — API keys, tokens, and private keys are stripped from all audit logs
- **Full audit trail** — every plugin run is logged to `.safeclaw/audit.jsonl`

See [SECURITY.md](SECURITY.md) for the full threat model.

## Configuration

SafeClaw is configured via `policy.yaml`:

```yaml
project_root: "."
allow_network: false
allow_shell: false
allowed_plugins:
  - todo_scan
  - log_summarize
  - secrets_scan
  - deps_audit
  - repo_stats
limits:
  max_file_mb: 5
  max_files: 2000
  timeout_seconds: 30
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `todo_scan` | Find TODO / FIXME / HACK markers |
| `log_summarize` | Extract errors and exceptions from log files |
| `secrets_scan` | Detect hardcoded API keys and credentials |
| `deps_audit` | Check declared dependencies for issues |
| `repo_stats` | Count files, lines of code, file type distribution |

## Why This Exists

Autonomous AI agents (like OpenClaw, PicoClaw, etc.) are powerful but often run with excessive privileges — unrestricted shell access, full disk access, and open network connections. SafeClaw demonstrates that a dev assistant can be **useful without being dangerous**, by enforcing least-privilege security at every layer.

This project was built as a portfolio project demonstrating understanding of security principles, clean architecture, and modern Python tooling.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Format check
ruff format --check .
```

## Contributing

Contributions are welcome! Please ensure all changes pass `ruff check` and `pytest` before submitting a PR.

## License

MIT
