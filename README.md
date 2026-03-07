# SafeClaw

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![CI](https://img.shields.io/github/actions/workflow/status/constripacity/safeclaw/ci.yml?label=CI)

A **sandboxed, policy-driven local dev assistant** that scans your codebase for TODOs, secrets, dependency issues, and more — without ever running arbitrary shell commands or accessing the network.

## Getting Started

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Navigate to your project

```bash
cd /path/to/your/project
```

### 3. Run SafeClaw

```bash
safeclaw
```

This displays the SafeClaw welcome screen with all available commands.

### 4. Scan your code

```bash
safeclaw todo .           # Find TODO/FIXME/HACK markers
safeclaw secrets .        # Check for hardcoded secrets and API keys
safeclaw deps .           # Audit your declared dependencies
safeclaw stats .          # Get repository statistics
safeclaw summarize build.log  # Summarise a build log
```

Each scan produces a bordered output panel and is automatically logged to the audit trail.

### 5. Review the audit log

```bash
safeclaw audit            # View recent entries
safeclaw audit -n 50      # View last 50 entries
```

### 6. Check your security policy

```bash
safeclaw policy
```

All permissions are denied by default. SafeClaw only does what `policy.yaml` explicitly allows.

## Quick Reference

```bash
# Core scans
safeclaw todo ./my-project/        # TODO/FIXME/HACK markers
safeclaw secrets ./my-project/     # Hardcoded secrets
safeclaw summarize ./build.log     # Log file errors
safeclaw deps ./my-project/        # Dependency issues
safeclaw stats ./my-project/       # Repository statistics

# Audit & policy
safeclaw audit                     # View audit log
safeclaw policy                    # Show current policy
safeclaw export --format html      # Export audit log

# Git integration
safeclaw init                      # Install pre-commit hook
safeclaw deinit                    # Remove pre-commit hook

# File watcher
safeclaw watch ./my-project/       # Auto-run on file changes

# LLM planner (requires Ollama)
safeclaw plan "scan for security issues"

# Web dashboard
safeclaw dashboard                 # Start localhost dashboard

# Multi-project management
safeclaw projects add myapp ./path/to/myapp
safeclaw projects scan-all

# AI fix suggestions (requires Ollama)
safeclaw fix all ./my-project/

# MCP server for Claude Code
safeclaw mcp --list-tools

# Interactive terminal UI
safeclaw tui
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

## LLM Planner (Phase 2)

SafeClaw includes an optional LLM-powered planner that turns natural language tasks into validated execution plans.

```bash
# Generate and execute a plan
safeclaw plan "scan this repo for security issues"

# Preview a plan without executing
safeclaw plan --dry-run "check code quality"
```

The LLM can only **suggest** actions — SafeClaw validates every step against your policy before anything runs. Supports Ollama (local), OpenAI, and Anthropic backends.

```yaml
# Enable in policy.yaml:
planner:
  enabled: true
  backend: "ollama"       # or "openai" / "anthropic"
  model: "qwen2.5-coder:14b"
  base_url: "http://localhost:11434"
  max_steps: 5
  require_confirmation: true
```

See [docs/planner-guide.md](docs/planner-guide.md) for setup details.

## Web Dashboard (Phase 2)

A localhost-only web UI for monitoring runs, viewing audit logs, and checking policy status.

```bash
# Start the dashboard
safeclaw dashboard

# Start with the premium gold-themed UI
safeclaw dashboard --golden
```

Binds to `127.0.0.1:8321` only. Protected by a bearer token generated on first run.

```yaml
# Enable in policy.yaml:
dashboard:
  enabled: true
  host: "127.0.0.1"
  port: 8321
```

## Pre-Commit Hook

SafeClaw can install a git pre-commit hook that automatically scans staged files for secrets before each commit.

```bash
# Install the hook
safeclaw init

# Remove the hook
safeclaw deinit
```

The hook scans only staged files (not the full project tree) for speed. If secrets are detected, the commit is blocked. Use `--force` to replace an existing SafeClaw hook section.

## Audit Export

Export your audit log to CSV, JSON, or HTML for reporting or analysis.

```bash
# Print JSON to stdout
safeclaw export --format json --count 10

# Write CSV to file
safeclaw export report.csv --format csv

# Generate a standalone dark-themed HTML report
safeclaw export report.html --format html --count 50
```

## File Watcher

Watch a directory and automatically run plugins when files change.

```bash
# Watch with all allowed plugins
safeclaw watch ./my-project/

# Watch with specific plugins only
safeclaw watch ./my-project/ --plugins todo_scan,secrets_scan --debounce 2.0
```

Requires the `watchdog` extra: `pip install -e ".[watch]"`

## Multi-Project Manager

Manage and scan multiple repositories from a single SafeClaw instance.

```bash
# Register projects
safeclaw projects add myapp /path/to/myapp --plugins todo_scan,secrets_scan
safeclaw projects add backend /path/to/backend --plugins todo_scan,deps_audit

# List all registered projects
safeclaw projects list

# Scan a specific project
safeclaw projects scan myapp

# Scan all projects with auto_scan enabled
safeclaw projects scan-all

# Summary report across all projects
safeclaw projects report
```

Project registry is stored at `~/.safeclaw/projects.yaml`. Each project gets its own temporary policy with `project_root` set to the project's path — all scans go through the existing policy-enforced runner.

## Smart Fix Suggestions

Uses your local Ollama instance to analyze scan findings and suggest concrete fixes.

```bash
# Scan for TODOs then get AI fix suggestions
safeclaw fix todo ./my-project/

# Scan for secrets then get AI remediation advice
safeclaw fix secrets ./my-project/

# Check deps then get AI upgrade suggestions
safeclaw fix deps ./my-project/

# Run all scans then get combined AI analysis
safeclaw fix all ./my-project/
```

Requires the planner to be enabled in policy.yaml and Ollama running locally. Findings are redacted before being sent to the LLM, and all requests are audit-logged.

## MCP Server (Claude Code Integration)

Expose SafeClaw as an MCP (Model Context Protocol) server so Claude Code can use it as a tool.

```bash
# List all available MCP tools
safeclaw mcp --list-tools

# Print setup instructions for Claude Code
safeclaw mcp --setup

# Start the MCP server (stdio mode)
safeclaw mcp
```

Add to your `.claude/settings.json`:

```json
{
  "mcpServers": {
    "safeclaw": {
      "command": "/path/to/.venv/bin/safeclaw",
      "args": ["mcp"]
    }
  }
}
```

Then in Claude Code: *"Use safeclaw to scan this project for secrets"*

10 tools are exposed: `safeclaw_todo`, `safeclaw_secrets`, `safeclaw_stats`, `safeclaw_deps`, `safeclaw_summarize`, `safeclaw_policy`, `safeclaw_audit`, `safeclaw_plan`, `safeclaw_fix`, `safeclaw_scan_all_projects`.

## Terminal UI (Phase 3)

A full-screen interactive terminal UI built with Textual, featuring three tabs: Scanner, Audit Log, and Planner.

```bash
safeclaw tui
```

Keyboard shortcuts: F1=Todo, F2=Secrets, F3=Stats, F4=Deps, F5=Log, Q=Quit.

## Why This Exists

Autonomous AI agents (like OpenClaw, PicoClaw, etc.) are powerful but often run with excessive privileges — unrestricted shell access, full disk access, and open network connections. SafeClaw demonstrates that a dev assistant can be **useful without being dangerous**, by enforcing least-privilege security at every layer.

This project was built as a portfolio project demonstrating understanding of security principles, clean architecture, and modern Python tooling.

## Companion Project: Quantum ML for Cybersecurity

SafeClaw's security-first philosophy extends into quantum computing research.
A companion project applies a **Variational Quantum Classifier (VQC)** to
network intrusion detection using the NSL-KDD dataset, executed on real
IBM Quantum hardware (ibm_fez — Heron r2 processor, 156 qubits).

**Key results:**

| Method | Accuracy |
|--------|----------|
| Classical SVM (RBF) | 82.0% |
| Classical Random Forest | 94.0% |
| VQC Simulator (4 qubits, 12 params) | 78.0% |
| VQC on IBM QPU | 4/100 iterations (877s QPU time) |

The quantum classifier achieves 78% accuracy with only 12 trainable
parameters — demonstrating that quantum feature spaces can capture
meaningful patterns in network security data. The full pipeline was
validated end-to-end on real quantum hardware with dynamical decoupling
and measurement twirling noise mitigation.

This research explores whether quantum advantage could emerge for
cybersecurity classification tasks as quantum hardware scales beyond
the current NISQ era.

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
