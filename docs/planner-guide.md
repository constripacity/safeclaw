# LLM Planner Guide

## How It Works

The planner follows a strict **suggest → validate → execute** flow:

```
User: "scan this repo for security issues"
  → Planner sends task + available plugins + policy to LLM
  → LLM returns JSON plan: [{"plugin": "secrets_scan", "target": "./"}]
  → SafeClaw validates each step against policy
  → Only approved steps execute
  → Results displayed to user
```

The LLM can only suggest actions from the allowed plugin list. It cannot:
- Run plugins not in `allowed_plugins`
- Access files outside `project_root`
- Execute shell commands
- Make network calls (unless policy allows)

## Backend Setup

### Ollama (Local — Recommended)

No API key needed. Install [Ollama](https://ollama.ai) and pull a model:

```bash
ollama pull qwen2.5-coder:14b
```

Policy configuration:

```yaml
planner:
  enabled: true
  backend: "ollama"
  model: "qwen2.5-coder:14b"
  base_url: "http://localhost:11434"
  require_confirmation: true
```

Ollama on localhost works even when `allow_network: false`.

### OpenAI

Set your API key as an environment variable:

```bash
export OPENAI_API_KEY=sk-...
```

Policy configuration:

```yaml
allow_network: true  # required for cloud APIs
planner:
  enabled: true
  backend: "openai"
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"
  require_confirmation: true
```

### Anthropic

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Policy configuration:

```yaml
allow_network: true
planner:
  enabled: true
  backend: "anthropic"
  model: "claude-sonnet-4-20250514"
  api_key_env: "ANTHROPIC_API_KEY"
  require_confirmation: true
```

## Usage

```bash
# Generate and execute a plan (with confirmation prompt)
safeclaw plan "scan for TODOs and check for secrets"

# Preview without executing
safeclaw plan --dry-run "audit this project"

# Skip confirmation (only if require_confirmation: false)
safeclaw plan --auto "run all scans"
```

## Example Output

```
         Execution Plan
+---+--------------+------+------------------------+---------+
| # | Plugin       | Target | Reason               | Status  |
+---+--------------+------+------------------------+---------+
| 1 | todo_scan    | ./   | Find open tasks        | allowed |
| 2 | secrets_scan | ./   | Check for leaked keys  | allowed |
| 3 | repo_stats   | ./   | Get project overview   | allowed |
+---+--------------+------+------------------------+---------+

Execute this plan? [y/n]: y

  Step 1 (todo_scan): OK
  Step 2 (secrets_scan): OK
  Step 3 (repo_stats): OK

3/3 step(s) completed successfully.
```

## Security Model

- **Plan validation**: Every step is checked against the plugin allowlist and path restrictions
- **Confirmation required**: By default, plans must be confirmed before execution
- **Max steps limit**: Plans exceeding `max_steps` are rejected entirely
- **API keys in env vars**: Keys are never stored in config files — read from environment variables
- **Audit logging**: All planner activity is logged with automatic secret redaction
- **No direct execution**: The LLM output is parsed as JSON, not evaluated as code
