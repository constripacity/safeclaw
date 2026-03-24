# SafeClaw – Project Context for Claude Code

## What This Is
SafeClaw is a **sandboxed local dev assistant** — a Python CLI tool inspired by OpenClaw/PicoClaw-style AI agents, but built with security-first principles. It's designed as a portfolio project that demonstrates:

- CLI design with Typer + Rich
- Policy-driven security (least privilege)
- Audit logging with secret redaction
- Plugin architecture
- Optional LLM planning layer (LLM suggests → policy decides)
- Testing + CI/CD

## Tech Stack
- **Python 3.11+**
- **Typer** – CLI framework
- **Pydantic v2** – config validation
- **PyYAML** – policy files
- **Rich** – terminal output formatting
- **FastAPI** (Phase 2) – optional local web dashboard
- **Textual** (Phase 3) – terminal UI framework (by Rich creators)
- **watchdog** (Phase 4) – cross-platform file system monitoring
- **MCP SDK** (Phase 4) – Model Context Protocol server for Claude Code
- **httpx** – HTTP client for Ollama/API calls
- **pytest** – testing
- **Ruff** – linting

## Architecture Principles
1. **No shell execution by default** – `allow_shell: false` in policy.yaml
2. **No network by default** – `allow_network: false` in policy.yaml
3. **Path enforcement** – all operations restricted to `project_root`
4. **Audit everything** – every plugin run logged to `.safeclaw/audit.jsonl`
5. **Redact secrets** – API keys, tokens, private keys stripped from logs
6. **Plugin allowlist** – only explicitly permitted plugins can run
7. **LLM can suggest, never execute** – optional planner outputs JSON plans validated against policy before execution

## Directory Structure
```
safeclaw/
├── CLAUDE.md                  # This file
├── README.md
├── README.de.md               # German version
├── pyproject.toml
├── policy.yaml
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── SECURITY.md                # Threat model documentation
├── docs/
│   ├── architecture.md
│   ├── threat-model.md
│   └── plugin-guide.md
├── safeclaw/
│   ├── __init__.py
│   ├── cli.py                 # Typer CLI entry point (20+ commands)
│   ├── policy.py              # Policy loading + validation
│   ├── audit.py               # Audit logging
│   ├── redaction.py           # Secret pattern redaction
│   ├── runner.py              # Plugin executor + policy enforcement
│   ├── hooks.py               # Pre-commit hook install/uninstall/run
│   ├── export.py              # Audit log export (CSV/JSON/HTML)
│   ├── watcher.py             # (Phase 4, local) Watchdog-based file watcher
│   ├── projects.py            # (Phase 4, local) Multi-project manager
│   ├── fixer.py               # (Phase 4, local) AI fix suggestions via Ollama
│   ├── mcp_server.py          # (Phase 4, local) MCP server for Claude Code
│   ├── planner.py             # (Phase 2) LLM planner module
│   ├── dashboard.py           # (Phase 2+3) FastAPI web UI + /api/* + /golden
│   ├── tui.py                 # (Phase 3) Textual terminal UI (public)
│   ├── templates/
│   │   ├── dashboard.html     # (Phase 3) Premium SPA web dashboard (public)
│   │   └── golden.html        # (Phase 3, local only) Gold/dark web dashboard
│   └── plugins/
│       ├── __init__.py
│       ├── base.py            # Plugin base class / interface
│       ├── todo_scan.py       # Scan for TODO/FIXME/HACK
│       ├── log_summarize.py   # Summarize build logs
│       ├── secrets_scan.py    # Detect leaked secrets
│       ├── deps_audit.py      # Check for outdated/vulnerable deps
│       ├── repo_stats.py      # Lines of code, file types, repo health
│       ├── license_check.py   # (Phase 5) Check license files + type detection
│       ├── complexity_scan.py # (Phase 5) AST-based code complexity analysis
│       └── git_history.py     # (Phase 5) Git history via .git directory reading
├── Dockerfile                 # (Phase 5) Multi-stage Docker build
├── .dockerignore              # (Phase 5) Docker exclusions
├── tests/
│   ├── conftest.py
│   ├── test_redaction.py
│   ├── test_policy.py
│   ├── test_runner.py
│   ├── test_cli.py
│   ├── test_dashboard.py
│   ├── test_planner.py
│   ├── test_audit.py
│   ├── test_hooks.py
│   ├── test_export.py
│   ├── test_integration.py    # (Phase 5) End-to-end integration tests
│   ├── test_watcher.py
│   ├── test_projects.py
│   ├── test_fixer.py
│   ├── test_mcp_server.py
│   ├── test_plugins/
│   │   ├── test_todo_scan.py
│   │   ├── test_secrets_scan.py
│   │   ├── test_log_summarize.py
│   │   ├── test_deps_audit.py
│   │   ├── test_repo_stats.py
│   │   ├── test_license_check.py    # (Phase 5)
│   │   ├── test_complexity_scan.py  # (Phase 5)
│   │   └── test_git_history.py      # (Phase 5)
│   └── ...
└── examples/
    ├── sample-repo/            # Dummy repo for demo runs
    │   ├── main.py
    │   ├── .env.example
    │   └── build.log
    └── demo.sh                 # One-liner demo script
```

> **Note:** `safeclaw/templates/golden.html`, `safeclaw/static/`, and all Phase 4 files (`projects.py`, `watcher.py`, `fixer.py`, `mcp_server.py` + their tests) are gitignored — they are local-only files that do not get pushed to GitHub. `safeclaw/tui.py` and `safeclaw/templates/dashboard.html` are public and tracked in git.

## Coding Conventions
- Use type hints everywhere
- Docstrings on all public functions (Google style)
- No `# type: ignore` without explanation
- All paths use `pathlib.Path`, never string concatenation
- Never store secrets in code — use redaction patterns
- Test coverage target: >90%
- Line length: 100 (Ruff config)

## Development Phases

### Phase 1: Core CLI + Plugins (MVP)
- [x] Project structure + pyproject.toml
- [x] policy.py — load and validate policy.yaml with Pydantic
- [x] redaction.py — regex-based secret stripping
- [x] audit.py — append-only JSONL audit log
- [x] runner.py — plugin executor with policy checks + path enforcement
- [x] cli.py — Typer commands: `todo`, `summarize`, `secrets`, `deps`, `stats`
- [x] Plugins: todo_scan, log_summarize, secrets_scan, deps_audit, repo_stats
- [x] Tests for all core modules
- [x] GitHub Actions CI (pytest + ruff)
- [x] README.md (English) + README.de.md (German)
- [x] SECURITY.md with threat model
- [x] Example sample-repo for demos

### Phase 2: LLM Planner + Web Dashboard
- [x] planner.py — sends task to LLM, receives JSON plan, validates against policy
- [x] Support OpenAI, Anthropic, and local Ollama endpoints
- [x] dashboard.py — FastAPI localhost UI showing recent runs, policy status, audit log
- [x] `safeclaw plan "task description"` CLI command
- [x] `safeclaw dashboard` CLI command
- [x] Dashboard bearer token auth + localhost binding
- [x] Planner + dashboard tests
- [x] docs/planner-guide.md

### Phase 3: Local UIs (local-only, gitignored)
- [x] `safeclaw tui` — full-screen Textual app (Scanner, Audit Log, Planner tabs)
- [x] `safeclaw dashboard --golden` — premium gold/dark web dashboard (single HTML file)
- [x] `/api/*` JSON endpoints added to dashboard.py (status, audit, plugins, policy, scan, plan, plan/execute)
- [x] Gold/dark color scheme (#0a0a0a bg, #d4a843 gold accents)
- [x] F1-F5 keyboard shortcuts in TUI, bearer token auth in web UI
- [x] All local UI files gitignored — never pushed to GitHub

### Phase 4: Utilities & Integrations
- [x] `safeclaw export` — audit log export to CSV, JSON, or HTML
- [x] `safeclaw watch` — watchdog-based file watcher with auto plugin runs
- [x] `safeclaw init` / `safeclaw deinit` — pre-commit hook integration (secrets_scan on staged files)
- [x] `safeclaw projects` — multi-project manager (add/remove/scan/scan-all/report)
- [x] `safeclaw fix` — AI-powered fix suggestions via Ollama (todo/secrets/deps/all)
- [x] `safeclaw mcp` — MCP server exposing 10 tools to Claude Code (stdio transport)
- [x] 297 tests passing, coverage target maintained

### Phase 5: Docker, New Plugins, Hardening (v0.4.0)
- [x] `license_check` plugin — detect LICENSE files and identify license type (MIT, Apache, GPL, etc.)
- [x] `complexity_scan` plugin — AST-based code complexity analysis (line count, params, nesting depth)
- [x] `git_history` plugin — analyze git history by reading .git directory directly (no shell)
- [x] `safeclaw license`, `safeclaw complexity`, `safeclaw git-history` CLI commands
- [x] Dashboard rate limiting (60 GET/min, 30 POST/min per IP, sliding window)
- [x] Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP, Cache-Control)
- [x] `/health` endpoint (no auth required) for Docker HEALTHCHECK
- [x] Audit log rotation (`rotate_audit()`, auto-rotate at 10MB, `safeclaw audit --rotate`)
- [x] Dockerfile (multi-stage, non-root user, HEALTHCHECK) + .dockerignore
- [x] 23 end-to-end integration tests (tests/test_integration.py)
- [x] 356 tests passing, CI green on Python 3.11 + 3.12

## Key Concepts Demonstrated
This project demonstrates understanding of:
- **Least privilege principle** — agent can only do what policy explicitly allows
- **Defense in depth** — path restriction + plugin allowlist + audit logging + redaction
- **Prompt injection awareness** — LLM planner can only suggest, never execute directly
- **Supply chain security** — no arbitrary third-party plugin execution
- **DevOps fundamentals** — CI/CD, Docker, linting, testing
- **Clean architecture** — separation of concerns, plugin system, config validation
- **Git integration** — pre-commit hooks for automated secret scanning
- **Multi-project management** — registry-based scanning across multiple repos
- **AI-assisted remediation** — Ollama-powered fix suggestions with severity ranking
- **Tool interoperability** — MCP server enabling Claude Code to use SafeClaw as a tool
