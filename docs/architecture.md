# SafeClaw Architecture

## Overview

SafeClaw follows a layered architecture with strict separation of concerns. Every component enforces the principle of least privilege.

## Component Diagram

```
                    +--------------------+
                    |   CLI / Dashboard  |
                    | cli.py  dashboard.py|
                    +--------+-----------+
                             |
                +------------+------------+
                |                         |
                v                         v
       +--------+---------+     +---------+--------+
       |     Runner        |     |     Planner      |
       | safeclaw/runner.py|     | safeclaw/planner.py|
       +--------+---------+     +---------+--------+
                |                         |
  +-------------+-------------+           |
  |             |              |          v
  v             v              v    +-----+------+
+------+---+  +-----+----+  +------+-----+  | LLM Backend |
|  Policy   |  |  Audit   |  |  Plugins   |  | (Ollama /   |
| policy.py |  | audit.py |  | plugins/*  |  |  OpenAI /   |
+------+---+  +-----+----+  +------+-----+  |  Anthropic) |
       |             |                        +-------------+
       v             v
+------+---+  +-----+------+
|policy.yaml|  |.safeclaw/  |
+-----------+  |audit.jsonl |
               +------------+
```

## Data Flow

### Direct Plugin Execution
1. **User** invokes a CLI command (e.g. `safeclaw todo ./src/`)
2. **CLI** loads the policy file and passes control to the **Runner**
3. **Runner** performs three checks:
   - Is the plugin in the allowed list? (policy check)
   - Does the plugin exist in the registry? (existence check)
   - Is the target path inside the project root? (path enforcement)
4. If all checks pass, the **Plugin** executes against the target
5. The **Plugin** returns a message and list of touched files
6. The **Runner** writes an **Audit** event (with automatic secret redaction)
7. The **CLI** formats and displays the result using Rich

### LLM Planner Flow (Phase 2)
1. **User** runs `safeclaw plan "task description"`
2. **Planner** builds a system prompt with available plugins and policy constraints
3. **Planner** sends the request to the configured LLM backend
4. **LLM** returns a JSON execution plan
5. **Planner** parses the JSON and validates each step against policy
6. If `require_confirmation` is true, the user must approve the plan
7. **Runner** executes each validated step sequentially (fail-fast)
8. All activity is logged to the audit log

### Dashboard Flow (Phase 2)
1. **User** starts the dashboard with `safeclaw dashboard`
2. **FastAPI** app binds to localhost only (127.0.0.1)
3. All requests require a bearer token (generated on first run)
4. Dashboard provides read access to audit logs, policy, and plugin status
5. POST endpoints allow running plugins and generating plans via API
6. All dashboard requests are logged to the audit log

## Key Design Decisions

### Policy as Configuration
All security decisions are driven by `policy.yaml`. There are no hardcoded permissions — the policy file is the single source of truth for what SafeClaw is allowed to do.

### Plugin Registry
Plugins are registered in a central dict inside `runner.py`. This prevents dynamic loading of arbitrary code while keeping the architecture extensible.

### Redaction Pipeline
All text passing through the audit system is automatically scanned for secret patterns (API keys, tokens, private keys) and replaced with `[REDACTED:PATTERN_NAME]` markers before being written to disk.

### Path Enforcement
Every target path is resolved to an absolute path and validated with `Path.relative_to(root)`. If the target is outside the project root, the operation is denied before any file I/O occurs.

### LLM Suggest, Never Execute
The planner parses LLM output as JSON data, never as code. Every suggested action must pass through the same policy checks as direct CLI invocations.

### Localhost-Only Dashboard
The dashboard binds exclusively to 127.0.0.1 and requires bearer token authentication. It is never exposed to the network.

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `cli.py` | User interface, argument parsing, output formatting |
| `policy.py` | Load, validate, and expose security policy |
| `runner.py` | Plugin dispatch, policy enforcement, error handling |
| `audit.py` | Append-only logging with redaction |
| `redaction.py` | Regex-based secret pattern matching and replacement |
| `planner.py` | LLM communication, plan parsing, plan validation |
| `dashboard.py` | FastAPI web UI, token auth, REST endpoints |
| `plugins/base.py` | Plugin interface definition |
| `plugins/*.py` | Individual plugin implementations |
