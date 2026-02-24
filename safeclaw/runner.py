"""Plugin executor — runs plugins with policy enforcement and audit logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from safeclaw.audit import AuditEvent, write_audit
from safeclaw.policy import Policy


@dataclass
class RunResult:
    """Result of a plugin execution."""

    ok: bool
    message: str
    touched_files: list[str] = field(default_factory=list)


# Plugin registry: maps plugin names to their run functions.
# Populated at import time by _register_builtins().
_PLUGIN_REGISTRY: dict[str, object] = {}


def _register_builtins() -> None:
    """Lazily import and register all built-in plugins."""
    if _PLUGIN_REGISTRY:
        return

    from safeclaw.plugins import deps_audit, log_summarize, repo_stats, secrets_scan, todo_scan

    _PLUGIN_REGISTRY.update(
        {
            "todo_scan": todo_scan.run,
            "log_summarize": log_summarize.run,
            "secrets_scan": secrets_scan.run,
            "deps_audit": deps_audit.run,
            "repo_stats": repo_stats.run,
        }
    )


def get_registry() -> dict[str, object]:
    """Return the plugin registry, initialising if needed."""
    _register_builtins()
    return _PLUGIN_REGISTRY


def run_plugin(policy: Policy, plugin_name: str, target_path: Path | str) -> RunResult:
    """Execute a plugin after validating it against policy.

    Checks performed:
    1. Plugin name is in the policy's allowed list.
    2. Plugin exists in the registry.
    3. Target path is inside the project root.

    Args:
        policy: The active security policy.
        plugin_name: Name of the plugin to run.
        target_path: File or directory to pass to the plugin.

    Returns:
        A RunResult indicating success/failure plus output.
    """
    root = policy.root_path()

    # --- Policy checks ---
    if plugin_name not in policy.allowed_plugins:
        msg = f"Plugin '{plugin_name}' is not in the allowed list"
        write_audit(
            root,
            AuditEvent(
                action=plugin_name,
                status="denied",
                detail=msg,
            ),
        )
        return RunResult(ok=False, message=msg)

    registry = get_registry()
    if plugin_name not in registry:
        msg = f"Plugin '{plugin_name}' is not registered"
        write_audit(
            root,
            AuditEvent(
                action=plugin_name,
                status="error",
                detail=msg,
            ),
        )
        return RunResult(ok=False, message=msg)

    target = Path(target_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        msg = f"Target path '{target}' is outside project root '{root}'"
        write_audit(
            root,
            AuditEvent(
                action=plugin_name,
                status="denied",
                detail=msg,
            ),
        )
        return RunResult(ok=False, message=msg)

    # --- Execute plugin ---
    try:
        run_fn = registry[plugin_name]
        message, touched_files = run_fn(policy, target)  # type: ignore[operator]
        write_audit(
            root,
            AuditEvent(
                action=plugin_name,
                status="ok",
                detail=message,
                touched_files=touched_files,
            ),
        )
        return RunResult(ok=True, message=message, touched_files=touched_files)
    except Exception as exc:
        msg = f"Plugin '{plugin_name}' raised an exception: {exc}"
        write_audit(
            root,
            AuditEvent(
                action=plugin_name,
                status="error",
                detail=msg,
            ),
        )
        return RunResult(ok=False, message=msg)
