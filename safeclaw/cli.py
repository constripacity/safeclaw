"""SafeClaw CLI — Typer entry point with Rich formatting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from safeclaw.audit import read_audit
from safeclaw.policy import load_policy
from safeclaw.runner import run_plan, run_plugin

app = typer.Typer(
    name="safeclaw",
    help="SafeClaw — A sandboxed, policy-driven local dev assistant.",
    no_args_is_help=True,
)
console = Console()

_DEFAULT_POLICY = Path("policy.yaml")

PolicyOption = Annotated[
    Path,
    typer.Option("--policy", "-p", help="Path to policy.yaml"),
]


def _run_and_display(policy_path: Path, plugin: str, target: Path) -> None:
    """Load policy, run a plugin, and display the result."""
    policy = load_policy(policy_path)
    result = run_plugin(policy, plugin, target)
    if result.ok:
        console.print(Panel(result.message, title=f"[green]{plugin}[/green]", border_style="green"))
    else:
        console.print(Panel(result.message, title=f"[red]{plugin}[/red]", border_style="red"))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Phase 1 commands
# ---------------------------------------------------------------------------


@app.command()
def todo(
    path: Annotated[Path, typer.Argument(help="Directory or file to scan")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan for TODO / FIXME / HACK markers."""
    _run_and_display(policy, "todo_scan", path)


@app.command()
def summarize(
    logfile: Annotated[Path, typer.Argument(help="Log file to summarise")],
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Summarise a log file (extract errors, exceptions, failures)."""
    _run_and_display(policy, "log_summarize", logfile)


@app.command()
def secrets(
    path: Annotated[Path, typer.Argument(help="Directory or file to scan")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan for hardcoded secrets and credentials."""
    _run_and_display(policy, "secrets_scan", path)


@app.command()
def deps(
    path: Annotated[Path, typer.Argument(help="Project directory")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Audit declared dependencies for potential issues."""
    _run_and_display(policy, "deps_audit", path)


@app.command()
def stats(
    path: Annotated[Path, typer.Argument(help="Directory to analyse")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Show repository statistics (files, lines, types)."""
    _run_and_display(policy, "repo_stats", path)


@app.command()
def audit(
    policy: PolicyOption = _DEFAULT_POLICY,
    count: Annotated[int, typer.Option("--count", "-n", help="Number of entries")] = 20,
) -> None:
    """Show recent audit log entries."""
    pol = load_policy(policy)
    entries = read_audit(pol.root_path(), last_n=count)

    if not entries:
        console.print("[dim]No audit log entries found.[/dim]")
        return

    table = Table(title="Audit Log (most recent first)")
    table.add_column("Timestamp", style="cyan", no_wrap=True)
    table.add_column("Action", style="magenta")
    table.add_column("Status")
    table.add_column("Detail", max_width=60)

    for entry in entries:
        ts = entry.get("timestamp", "?")[:19]
        action = entry.get("action", "?")
        status = entry.get("status", "?")
        detail = entry.get("detail", "")[:60]
        style = "green" if status == "ok" else "red"
        table.add_row(ts, action, f"[{style}]{status}[/{style}]", detail)

    console.print(table)


@app.command(name="policy")
def show_policy(
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Display the current policy summary."""
    pol = load_policy(policy)

    table = Table(title="SafeClaw Policy")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Project root", str(pol.root_path()))
    table.add_row("Sandbox subdir", pol.sandbox_subdir)
    table.add_row(
        "Network access",
        "[green]allowed[/green]" if pol.allow_network else "[red]denied[/red]",
    )
    table.add_row(
        "Shell access",
        "[green]allowed[/green]" if pol.allow_shell else "[red]denied[/red]",
    )
    table.add_row("Allowed plugins", ", ".join(pol.allowed_plugins) or "(none)")
    table.add_row("Max file size", f"{pol.limits.max_file_mb} MB")
    table.add_row("Max files", str(pol.limits.max_files))
    table.add_row("Timeout", f"{pol.limits.timeout_seconds}s")
    table.add_row(
        "Planner",
        "[green]enabled[/green]" if pol.planner.enabled else "[dim]disabled[/dim]",
    )
    table.add_row(
        "Dashboard",
        "[green]enabled[/green]" if pol.dashboard.enabled else "[dim]disabled[/dim]",
    )

    console.print(table)


# ---------------------------------------------------------------------------
# Phase 2 commands
# ---------------------------------------------------------------------------


@app.command(name="plan")
def plan_cmd(
    task: Annotated[str, typer.Argument(help="Task description for the LLM planner")],
    policy: PolicyOption = _DEFAULT_POLICY,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show plan without executing")] = False,
    auto: Annotated[bool, typer.Option("--auto", help="Skip confirmation")] = False,
) -> None:
    """Generate and execute an LLM-powered execution plan."""
    from safeclaw.planner import (
        PlanConnectionError,
        Planner,
        PlannerDisabledError,
        PlanNetworkError,
        PlanParseError,
        validate_plan,
    )

    pol = load_policy(policy)

    try:
        planner = Planner(pol)
        exec_plan = planner.plan(task)
    except PlannerDisabledError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except PlanNetworkError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except PlanConnectionError as exc:
        console.print(f"[red]Connection error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except PlanParseError as exc:
        console.print(f"[red]Failed to parse LLM response: {exc}[/red]")
        if exc.raw_response:
            console.print(Panel(exc.raw_response[:500], title="Raw response"))
        raise typer.Exit(code=1) from exc

    # Validate the plan
    result = validate_plan(exec_plan, pol)

    # Display the plan as a table
    table = Table(title="Execution Plan")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Plugin", style="magenta")
    table.add_column("Target")
    table.add_column("Reason")
    table.add_column("Status")

    rejected_plugins = set()
    for rej in result.rejected_steps:
        # Extract plugin name from rejection messages
        if "'" in rej:
            rejected_plugins.add(rej.split("'")[1])

    for i, step in enumerate(exec_plan.steps, start=1):
        is_rejected = step.plugin in rejected_plugins or any(
            step.target in r for r in result.rejected_steps
        )
        status = "[red]denied[/red]" if is_rejected else "[green]allowed[/green]"
        table.add_row(str(i), step.plugin, step.target, step.reason, status)

    console.print(table)

    if result.rejected_steps:
        for msg in result.rejected_steps:
            console.print(f"  [red]Rejected:[/red] {msg}")

    if not result.validated:
        console.print("\n[red]Plan validation failed. No steps will be executed.[/red]")
        raise typer.Exit(code=1)

    if dry_run:
        console.print("\n[dim]Dry run — no steps executed.[/dim]")
        return

    # Confirmation
    if pol.planner.require_confirmation and not auto:
        confirm = typer.confirm("Execute this plan?")
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return
    elif auto and pol.planner.require_confirmation:
        console.print("[red]Cannot use --auto when require_confirmation is true in policy.[/red]")
        raise typer.Exit(code=1)

    # Execute
    console.print("\n[bold]Executing plan...[/bold]\n")
    results = run_plan(pol, exec_plan)

    for i, (step, res) in enumerate(zip(exec_plan.steps, results, strict=False), start=1):
        icon = "[green]OK[/green]" if res.ok else "[red]FAIL[/red]"
        console.print(f"  Step {i} ({step.plugin}): {icon}")
        if not res.ok:
            console.print(f"    {res.message}")
            break

    ok_count = sum(1 for r in results if r.ok)
    console.print(f"\n{ok_count}/{len(results)} step(s) completed successfully.")


@app.command(name="dashboard")
def dashboard_cmd(
    policy: PolicyOption = _DEFAULT_POLICY,
    port: Annotated[int, typer.Option("--port", help="Port to bind to")] = 0,
) -> None:
    """Start the SafeClaw web dashboard (localhost only)."""
    from safeclaw.dashboard import create_app, get_or_create_token

    pol = load_policy(policy)

    if not pol.dashboard.enabled:
        console.print(
            "[red]Dashboard is disabled in policy.yaml. "
            "Set dashboard.enabled: true to use this feature.[/red]"
        )
        raise typer.Exit(code=1)

    bind_port = port if port else pol.dashboard.port
    host = pol.dashboard.host
    token = get_or_create_token(pol.root_path())

    console.print("\n[bold]SafeClaw Dashboard[/bold]")
    console.print(f"  URL:   http://{host}:{bind_port}")
    console.print(f"  Token: {token}\n")

    import uvicorn

    uvicorn.run(create_app(pol), host=host, port=bind_port, log_level="warning")
