# Writing a SafeClaw Plugin

This guide explains how to create a new plugin for SafeClaw.

## Plugin Interface

Every plugin is a Python module in `safeclaw/plugins/` that exposes a single `run` function:

```python
from pathlib import Path
from safeclaw.policy import Policy


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Execute the plugin.

    Args:
        policy: The active security policy. Use this for limits,
                project root path, and other configuration.
        target: The file or directory to operate on.

    Returns:
        A tuple of:
        - A human-readable message describing the results.
        - A list of file paths that were read or modified.
    """
    ...
```

## Step-by-Step

### 1. Create the Plugin Module

Create a new file in `safeclaw/plugins/`, e.g. `my_plugin.py`:

```python
"""Plugin: description of what it does."""

from __future__ import annotations

from pathlib import Path

from safeclaw.policy import Policy


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """One-line description."""
    max_mb = policy.limits.max_file_mb
    max_files = policy.limits.max_files

    # Your logic here...

    return "Results summary", ["list", "of", "touched", "files"]
```

### 2. Register the Plugin

Open `safeclaw/runner.py` and add your plugin to the `_register_builtins()` function:

```python
def _register_builtins() -> None:
    from safeclaw.plugins import my_plugin  # add this import

    _PLUGIN_REGISTRY.update({
        # ... existing plugins ...
        "my_plugin": my_plugin.run,          # add this entry
    })
```

### 3. Allow the Plugin in Policy

Add the plugin name to `policy.yaml`:

```yaml
allowed_plugins:
  - todo_scan
  - my_plugin  # add this
```

### 4. Add a CLI Command (Optional)

Add a new command in `safeclaw/cli.py`:

```python
@app.command()
def mycommand(
    path: Annotated[Path, typer.Argument(help="Target path")] = Path("."),
    policy: PolicyOption = _default_policy(),
) -> None:
    """Description of the command."""
    _run_and_display(policy, "my_plugin", path)
```

## Guidelines

- **Respect limits**: Always check `policy.limits.max_file_mb` and `policy.limits.max_files`
- **No shell commands**: Plugins must not invoke subprocesses
- **No network**: Unless the policy explicitly allows it (check `policy.allow_network`)
- **Use pathlib**: All path operations should use `pathlib.Path`
- **Handle errors gracefully**: Return a helpful message rather than raising exceptions
- **Report touched files**: List every file your plugin reads or modifies
- **Type hints**: Use type hints on all functions
- **Docstrings**: Google-style docstrings on all public functions

## Testing

Create a test file in `tests/test_plugins/`:

```python
from pathlib import Path
from safeclaw.plugins.my_plugin import run
from safeclaw.policy import Policy


def test_basic(tmp_path: Path) -> None:
    # Create test fixtures
    (tmp_path / "test.py").write_text("content", encoding="utf-8")
    pol = Policy(project_root=str(tmp_path))
    message, touched = run(pol, tmp_path)
    assert "expected" in message
```
