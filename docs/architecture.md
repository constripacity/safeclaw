# SafeClaw Architecture

## Overview

SafeClaw follows a layered architecture with strict separation of concerns. Every component enforces the principle of least privilege.

## Component Diagram

```
                         +------------------+
                         |     CLI (Typer)   |
                         |    safeclaw/cli.py|
                         +--------+---------+
                                  |
                                  v
                         +--------+---------+
                         |     Runner       |
                         | safeclaw/runner.py|
                         +--------+---------+
                                  |
                    +-------------+-------------+
                    |             |              |
                    v             v              v
             +------+---+  +-----+----+  +------+-----+
             |  Policy   |  |  Audit   |  |  Plugins   |
             | policy.py |  | audit.py |  | plugins/*  |
             +------+---+  +-----+----+  +------+-----+
                    |             |
                    v             v
             +------+---+  +-----+------+
             |policy.yaml|  |.safeclaw/  |
             +-----------+  |audit.jsonl |
                            +------------+
```

## Data Flow

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

## Key Design Decisions

### Policy as Configuration
All security decisions are driven by `policy.yaml`. There are no hardcoded permissions — the policy file is the single source of truth for what SafeClaw is allowed to do.

### Plugin Registry
Plugins are registered in a central dict inside `runner.py`. This prevents dynamic loading of arbitrary code while keeping the architecture extensible.

### Redaction Pipeline
All text passing through the audit system is automatically scanned for secret patterns (API keys, tokens, private keys) and replaced with `[REDACTED:PATTERN_NAME]` markers before being written to disk.

### Path Enforcement
Every target path is resolved to an absolute path and validated with `Path.relative_to(root)`. If the target is outside the project root, the operation is denied before any file I/O occurs.

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `cli.py` | User interface, argument parsing, output formatting |
| `policy.py` | Load, validate, and expose security policy |
| `runner.py` | Plugin dispatch, policy enforcement, error handling |
| `audit.py` | Append-only logging with redaction |
| `redaction.py` | Regex-based secret pattern matching and replacement |
| `plugins/base.py` | Plugin interface definition |
| `plugins/*.py` | Individual plugin implementations |
