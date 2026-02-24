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
- **pytest** – testing
- **Ruff** – linting
- **Docker** (Phase 3) – sandboxed execution

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
├── Dockerfile
├── docker-compose.yml
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
│   ├── cli.py                 # Typer CLI entry point
│   ├── policy.py              # Policy loading + validation
│   ├── audit.py               # Audit logging
│   ├── redaction.py           # Secret pattern redaction
│   ├── runner.py              # Plugin executor + policy enforcement
│   ├── planner.py             # (Phase 2) LLM planner module
│   ├── dashboard.py           # (Phase 2) FastAPI local web UI
│   └── plugins/
│       ├── __init__.py
│       ├── base.py            # Plugin base class / interface
│       ├── todo_scan.py       # Scan for TODO/FIXME/HACK
│       ├── log_summarize.py   # Summarize build logs
│       ├── secrets_scan.py    # Detect leaked secrets
│       ├── deps_audit.py      # Check for outdated/vulnerable deps
│       └── repo_stats.py      # Lines of code, file types, repo health
├── tests/
│   ├── conftest.py
│   ├── test_redaction.py
│   ├── test_policy.py
│   ├── test_runner.py
│   ├── test_plugins/
│   │   ├── test_todo_scan.py
│   │   ├── test_secrets_scan.py
│   │   └── test_log_summarize.py
│   └── test_audit.py
└── examples/
    ├── sample-repo/            # Dummy repo for demo runs
    │   ├── main.py
    │   ├── .env.example
    │   └── build.log
    └── demo.sh                 # One-liner demo script
```

## Coding Conventions
- Use type hints everywhere
- Docstrings on all public functions (Google style)
- No `# type: ignore` without explanation
- All paths use `pathlib.Path`, never string concatenation
- Never store secrets in code — use redaction patterns
- Test coverage target: >80%
- Line length: 100 (Ruff config)

## Development Phases

### Phase 1: Core CLI + Plugins (MVP)
- [x] Project structure + pyproject.toml
- [ ] policy.py — load and validate policy.yaml with Pydantic
- [ ] redaction.py — regex-based secret stripping
- [ ] audit.py — append-only JSONL audit log
- [ ] runner.py — plugin executor with policy checks + path enforcement
- [ ] cli.py — Typer commands: `todo`, `summarize`, `secrets`, `deps`, `stats`
- [ ] Plugins: todo_scan, log_summarize, secrets_scan, deps_audit, repo_stats
- [ ] Tests for all core modules
- [ ] GitHub Actions CI (pytest + ruff)
- [ ] README.md (English) + README.de.md (German)
- [ ] SECURITY.md with threat model
- [ ] Example sample-repo for demos

### Phase 2: LLM Planner + Web Dashboard
- [ ] planner.py — sends task to LLM, receives JSON plan, validates against policy
- [ ] Support OpenAI, Anthropic, and local Ollama endpoints
- [ ] dashboard.py — FastAPI localhost UI showing recent runs, policy status, audit log
- [ ] `safeclaw plan "migrate this project to FastAPI"` CLI command

### Phase 3: Docker Sandboxing
- [ ] Dockerfile — run SafeClaw inside container
- [ ] docker-compose.yml — mount only project folder
- [ ] Document sandboxing approach in docs/

## Key Concepts Demonstrated
This project demonstrates understanding of:
- **Least privilege principle** — agent can only do what policy explicitly allows
- **Defense in depth** — path restriction + plugin allowlist + audit logging + redaction
- **Prompt injection awareness** — LLM planner can only suggest, never execute directly
- **Supply chain security** — no arbitrary third-party plugin execution
- **DevOps fundamentals** — CI/CD, Docker, linting, testing
- **Clean architecture** — separation of concerns, plugin system, config validation
