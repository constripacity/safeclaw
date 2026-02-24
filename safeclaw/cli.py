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
from safeclaw.runner import run_plugin

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

    console.print(table)
