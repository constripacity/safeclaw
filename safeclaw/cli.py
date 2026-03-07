"""SafeClaw CLI — Typer entry point with Rich formatting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from safeclaw import __version__
from safeclaw.audit import read_audit
from safeclaw.policy import load_policy
from safeclaw.runner import run_plan, run_plugin

app = typer.Typer(
    name="safeclaw",
    help="SafeClaw -- A sandboxed, policy-driven local dev assistant.",
    invoke_without_command=True,
)
console = Console()

_DEFAULT_POLICY = Path("policy.yaml")

PolicyOption = Annotated[
    Path,
    typer.Option("--policy", "-p", help="Path to policy.yaml"),
]

_BANNER = r"""[bold cyan]
  ____         __      ____  _
 / ___|  __ _ / _| ___|  _ \| | __ ___      __
 \___ \ / _` | |_ / _ \ |   | |/ _` \ \ /\ / /
  ___) | (_| |  _|  __/ |_  | | (_| |\ V  V /
 |____/ \__,_|_|  \___|____/|_|\__,_| \_/\_/
[/bold cyan]"""


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"SafeClaw v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """SafeClaw -- A sandboxed, policy-driven local dev assistant."""
    if ctx.invoked_subcommand is not None:
        return
    console.print(_BANNER)
    console.print(
        f"  [dim]v{__version__}[/dim]  [bold]Sandboxed, policy-driven local dev assistant[/bold]\n"
    )
    console.print("  [cyan]Usage:[/cyan]  safeclaw [COMMAND] [OPTIONS]\n")
    console.print("  [yellow]Core Scans[/yellow]")
    console.print("    todo        Scan for TODO/FIXME/HACK markers")
    console.print("    secrets     Scan for hardcoded secrets")
    console.print("    deps        Audit declared dependencies")
    console.print("    stats       Repository statistics")
    console.print("    summarize   Summarise a log file")
    console.print("    license     Check for license files")
    console.print("    complexity  Scan for code complexity issues")
    console.print("    git-history Analyze git history\n")
    console.print("  [yellow]Tools[/yellow]")
    console.print("    audit       View the audit log")
    console.print("    policy      Display current policy")
    console.print("    export      Export audit log (CSV/JSON/HTML)")
    console.print("    plan        LLM-powered execution plans")
    console.print("    watch       Auto-run plugins on file changes")
    console.print("    dashboard   Start the web dashboard\n")
    console.print(
        "  Run [bold]safeclaw --help[/bold] for all commands"
        " or [bold]safeclaw COMMAND --help[/bold] for details.\n"
    )


def _run_and_display(policy_path: Path, plugin: str, target: Path) -> None:
    """Load policy, run a plugin, and display the result."""
    policy = load_policy(policy_path)
    result = run_plugin(policy, plugin, target)
    if result.ok:
        title = f"[green]OK[/green] [bold]{plugin}[/bold]"
        console.print(Panel(result.message, title=title, border_style="green"))
    else:
        title = f"[red]FAIL[/red] [bold]{plugin}[/bold]"
        console.print(Panel(result.message, title=title, border_style="red"))
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


@app.command(name="license")
def license_cmd(
    path: Annotated[Path, typer.Argument(help="Project directory")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Check for license files and identify license type."""
    _run_and_display(policy, "license_check", path)


@app.command()
def complexity(
    path: Annotated[Path, typer.Argument(help="Directory or file to scan")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan Python files for code complexity issues."""
    _run_and_display(policy, "complexity_scan", path)


@app.command(name="git-history")
def git_history_cmd(
    path: Annotated[Path, typer.Argument(help="Repository directory")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Analyze git history (reads .git directory directly)."""
    _run_and_display(policy, "git_history", path)


@app.command()
def audit(
    policy: PolicyOption = _DEFAULT_POLICY,
    count: Annotated[int, typer.Option("--count", "-n", help="Number of entries")] = 20,
    rotate: Annotated[bool, typer.Option("--rotate", help="Rotate the audit log file")] = False,
) -> None:
    """Show recent audit log entries."""
    pol = load_policy(policy)

    if rotate:
        from safeclaw.audit import rotate_audit

        result = rotate_audit(pol.root_path())
        if result:
            console.print(f"[green]Audit log rotated to {result.name}[/green]")
        else:
            console.print("[dim]Nothing to rotate (audit log is empty or missing).[/dim]")
        return

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


@app.command(name="init")
def init_cmd(
    force: Annotated[bool, typer.Option("--force", help="Replace existing SafeClaw hook")] = False,
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Install the SafeClaw pre-commit hook into this git repository."""
    from safeclaw.hooks import install_hook

    pol = load_policy(policy)

    try:
        hook_path = install_hook(pol.root_path(), force=force)
    except (FileNotFoundError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]SafeClaw pre-commit hook installed at {hook_path}[/green]")


@app.command(name="deinit")
def deinit_cmd(
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Remove the SafeClaw pre-commit hook from this git repository."""
    from safeclaw.hooks import uninstall_hook

    pol = load_policy(policy)
    removed = uninstall_hook(pol.root_path())

    if removed:
        console.print("[green]SafeClaw pre-commit hook removed.[/green]")
    else:
        console.print("[yellow]No SafeClaw hook found to remove.[/yellow]")


@app.command(name="export")
def export_cmd(
    path: Annotated[
        Path | None,
        typer.Argument(help="Output file path (omit for stdout)"),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="Export format: csv, json, or html"),
    ] = "json",
    count: Annotated[int, typer.Option("--count", "-n", help="Number of entries")] = 50,
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Export audit log to CSV, JSON, or HTML."""
    from safeclaw.export import export_audit

    pol = load_policy(policy)

    try:
        result = export_audit(pol, fmt=fmt, count=count, output_path=path)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if path is None:
        console.print(result)
    else:
        console.print(f"[green]Exported {count} entries to {path}[/green]")


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
        with console.status(
            "[bold cyan]Generating plan...[/bold cyan]",
            spinner="dots",
        ):
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


@app.command(name="watch")
def watch_cmd(
    path: Annotated[Path, typer.Argument(help="Directory to watch")] = Path("."),
    plugins: Annotated[
        str | None,
        typer.Option("--plugins", help="Comma-separated plugin names (default: all allowed)"),
    ] = None,
    debounce: Annotated[
        float, typer.Option("--debounce", help="Debounce interval in seconds")
    ] = 2.0,
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Watch a directory and auto-run plugins on file changes."""
    from safeclaw.watcher import watch

    pol = load_policy(policy)
    plugin_list = [p.strip() for p in plugins.split(",") if p.strip()] if plugins else None

    try:
        watch(
            pol,
            path,
            plugins=plugin_list,
            debounce_ms=int(debounce * 1000),
            console=console,
        )
    except ImportError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


@app.command(name="tui")
def tui_cmd(
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Launch the interactive terminal UI."""
    from safeclaw.tui import run_tui

    run_tui(policy_path=policy)


@app.command(name="dashboard")
def dashboard_cmd(
    policy: PolicyOption = _DEFAULT_POLICY,
    port: Annotated[int, typer.Option("--port", help="Port to bind to")] = 0,
    golden: Annotated[bool, typer.Option("--golden", help="Use the premium gold web UI")] = False,
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

    ui_label = "Golden" if golden else "Standard"
    url_path = "/golden" if golden else "/"
    console.print(f"\n[bold]SafeClaw Dashboard[/bold] ({ui_label})")
    console.print(f"  URL:   http://{host}:{bind_port}{url_path}")
    console.print(f"  Token: {token}\n")

    import uvicorn

    uvicorn.run(create_app(pol, golden=golden), host=host, port=bind_port, log_level="warning")


# ---------------------------------------------------------------------------
# Phase 4 commands — multi-project
# ---------------------------------------------------------------------------

projects_app = typer.Typer(help="Multi-project management commands.")
app.add_typer(projects_app, name="projects")


def _get_project_manager(policy_path: Path) -> tuple:
    """Load policy, registry, and return (ProjectManager, policy)."""
    from safeclaw.projects import ProjectManager, load_projects

    pol = load_policy(policy_path)
    registry = load_projects()
    return ProjectManager(registry, pol), pol


@projects_app.command(name="list")
def projects_list(
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Show all registered projects."""
    mgr, _ = _get_project_manager(policy)
    projects = mgr.list_projects()

    if not projects:
        console.print("[dim]No projects registered. Use 'safeclaw projects add' to add one.[/dim]")
        return

    table = Table(title="Registered Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Plugins", style="magenta")
    table.add_column("Auto-Scan")
    table.add_column("Last Scan", style="dim")

    for proj in projects:
        auto = "[green]yes[/green]" if proj.auto_scan else "[red]no[/red]"
        last = mgr.get_last_scan_time(proj.name) or "never"
        table.add_row(proj.name, str(proj.path), ", ".join(proj.plugins), auto, last)

    console.print(table)


@projects_app.command(name="add")
def projects_add(
    name: Annotated[str, typer.Argument(help="Unique project name")],
    path: Annotated[Path, typer.Argument(help="Path to project directory")],
    plugins: Annotated[
        str | None,
        typer.Option("--plugins", help="Comma-separated plugin names"),
    ] = None,
    no_auto: Annotated[bool, typer.Option("--no-auto", help="Disable auto-scan")] = False,
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Register a new project."""
    from safeclaw.projects import save_projects

    mgr, _ = _get_project_manager(policy)
    plugin_list = [p.strip() for p in plugins.split(",") if p.strip()] if plugins else None

    try:
        config = mgr.add_project(name, path, plugins=plugin_list, auto_scan=not no_auto)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    save_projects(mgr.registry)
    console.print(f"[green]Added project '{config.name}' at {config.path}[/green]")


@projects_app.command(name="remove")
def projects_remove(
    name: Annotated[str, typer.Argument(help="Project name to remove")],
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Unregister a project."""
    from safeclaw.projects import save_projects

    mgr, _ = _get_project_manager(policy)
    removed = mgr.remove_project(name)

    if removed:
        save_projects(mgr.registry)
        console.print(f"[green]Removed project '{name}'.[/green]")
    else:
        console.print(f"[yellow]Project '{name}' not found.[/yellow]")


@projects_app.command(name="scan")
def projects_scan(
    name: Annotated[str, typer.Argument(help="Project name to scan")],
    plugin: Annotated[str | None, typer.Option("--plugin", help="Specific plugin to run")] = None,
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan a specific project with its configured plugins."""
    mgr, _ = _get_project_manager(policy)

    try:
        scan_result = mgr.scan_project(name, plugin_name=plugin)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"\n[bold]Scan results for '{name}'[/bold] ({scan_result.scan_time[:19]})\n")
    for r in scan_result.results:
        if r.ok:
            console.print(Panel(r.message, title="[green]OK[/green]", border_style="green"))
        else:
            console.print(Panel(r.message, title="[red]FAIL[/red]", border_style="red"))


@projects_app.command(name="scan-all")
def projects_scan_all(
    plugin: Annotated[str | None, typer.Option("--plugin", help="Specific plugin for all")] = None,
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan all auto_scan projects."""
    mgr, _ = _get_project_manager(policy)
    all_results = mgr.scan_all(plugin_name=plugin)

    if not all_results:
        msg = "No projects to scan (none registered or all have auto_scan=false)."
        console.print(f"[dim]{msg}[/dim]")
        return

    for proj_name, scan_result in all_results.items():
        ok = sum(1 for r in scan_result.results if r.ok)
        total = len(scan_result.results)
        status = "[green]OK[/green]" if ok == total else f"[yellow]{ok}/{total}[/yellow]"
        console.print(f"  {proj_name}: {status}")

    total_scans = sum(len(sr.results) for sr in all_results.values())
    total_ok = sum(sum(1 for r in sr.results if r.ok) for sr in all_results.values())
    n_proj = len(all_results)
    console.print(
        f"\n[bold]{total_ok}/{total_scans}[/bold] checks passed across {n_proj} project(s).",
    )


@projects_app.command(name="report")
def projects_report(
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Show a summary report across all projects."""
    mgr, _ = _get_project_manager(policy)
    report = mgr.get_report()

    if not report:
        console.print("[dim]No projects registered.[/dim]")
        return

    table = Table(title="Project Report")
    table.add_column("Project", style="cyan")
    table.add_column("Path")
    table.add_column("Plugins", style="magenta")
    table.add_column("Auto-Scan")
    table.add_column("Last Scan", style="dim")

    for name, info in report.items():
        auto = "[green]yes[/green]" if info["auto_scan"] else "[red]no[/red]"
        table.add_row(name, info["path"], ", ".join(info["plugins"]), auto, info["last_scan"])

    console.print(table)


# ---------------------------------------------------------------------------
# Phase 4 commands — smart fix suggestions
# ---------------------------------------------------------------------------

_SEVERITY_STYLES = {
    "critical": ("bold red", "RED"),
    "high": ("red", "RED"),
    "medium": ("yellow", "YLW"),
    "low": ("green", "GRN"),
    "info": ("dim", "INF"),
}

fix_app = typer.Typer(help="AI-powered fix suggestions (requires Ollama).")
app.add_typer(fix_app, name="fix")


def _display_suggestions(suggestions: object, model: str) -> None:
    """Render FixSuggestions as a Rich panel."""
    from safeclaw.fixer import FixSuggestions

    assert isinstance(suggestions, FixSuggestions)

    lines: list[str] = []
    for item in suggestions.findings:
        style, badge = _SEVERITY_STYLES.get(item.severity.lower(), ("dim", "???"))
        lines.append(f"[{style}]{badge} {item.severity.upper()}[/{style}] | {item.original}")
        lines.append(f"  [dim]Why:[/dim] {item.explanation}")
        lines.append(f"  [dim]Fix:[/dim] {item.fix}")
        lines.append("")

    if suggestions.summary:
        lines.append(f"[bold]Summary:[/bold] {suggestions.summary}")

    body = "\n".join(lines) if lines else "[dim]No suggestions generated.[/dim]"
    title = f"Smart Fix Suggestions (powered by {model})"
    console.print(Panel(body, title=title, border_style="yellow"))


def _fix_with_plugin(policy_path: Path, plugin: str, target: Path, fix_method: str) -> None:
    """Run a plugin scan, then feed results to SmartFixer."""
    from safeclaw.fixer import FixerConnectionError, FixerDisabledError, FixerParseError, SmartFixer

    pol = load_policy(policy_path)
    result = run_plugin(pol, plugin, target)

    if not result.ok:
        console.print(f"[red]Scan failed: {result.message}[/red]")
        raise typer.Exit(code=1)

    console.print(Panel(result.message, title=f"[green]{plugin}[/green]", border_style="green"))

    try:
        fixer = SmartFixer(pol)
        method = getattr(fixer, fix_method)
        with console.status(
            "[bold cyan]Analyzing with AI...[/bold cyan]",
            spinner="dots",
        ):
            suggestions = method(result.message)
    except FixerDisabledError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except FixerConnectionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except FixerParseError as exc:
        console.print(f"[red]Failed to parse AI response: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    _display_suggestions(suggestions, pol.planner.model)


@fix_app.command(name="todo")
def fix_todo(
    path: Annotated[Path, typer.Argument(help="Directory or file to scan")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan for TODOs then get AI fix suggestions."""
    _fix_with_plugin(policy, "todo_scan", path, "fix_todos")


@fix_app.command(name="secrets")
def fix_secrets(
    path: Annotated[Path, typer.Argument(help="Directory or file to scan")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Scan for secrets then get AI suggestions for proper handling."""
    _fix_with_plugin(policy, "secrets_scan", path, "fix_secrets")


@fix_app.command(name="deps")
def fix_deps(
    path: Annotated[Path, typer.Argument(help="Project directory")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Check deps then get AI suggestions for updates."""
    _fix_with_plugin(policy, "deps_audit", path, "fix_deps")


@fix_app.command(name="all")
def fix_all(
    path: Annotated[Path, typer.Argument(help="Directory to scan")] = Path("."),
    policy: PolicyOption = _DEFAULT_POLICY,
) -> None:
    """Run all scans then get combined AI analysis."""
    from safeclaw.fixer import FixerConnectionError, FixerDisabledError, FixerParseError, SmartFixer

    pol = load_policy(policy)

    # Run available scans and collect results
    scan_plugins = ["todo_scan", "secrets_scan", "deps_audit"]
    combined_output: list[str] = []

    for plugin in scan_plugins:
        if plugin not in pol.allowed_plugins:
            continue
        result = run_plugin(pol, plugin, path)
        if result.ok:
            combined_output.append(f"=== {plugin} ===\n{result.message}")

    if not combined_output:
        console.print("[dim]No scan results to analyze.[/dim]")
        return

    all_output = "\n\n".join(combined_output)
    console.print(
        Panel(
            all_output,
            title="[green]Combined Scan Results[/green]",
            border_style="green",
        )
    )
    try:
        fixer = SmartFixer(pol)
        with console.status(
            "[bold cyan]Analyzing with AI...[/bold cyan]",
            spinner="dots",
        ):
            suggestions = fixer.analyze_findings(
                all_output,
                context="Combined results from multiple SafeClaw security scans.",
            )
    except FixerDisabledError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except FixerConnectionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except FixerParseError as exc:
        console.print(f"[red]Failed to parse AI response: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    _display_suggestions(suggestions, pol.planner.model)


# ---------------------------------------------------------------------------
# Phase 4 commands — MCP server
# ---------------------------------------------------------------------------


@app.command(name="mcp")
def mcp_cmd(
    list_tools: Annotated[
        bool, typer.Option("--list-tools", help="List all available MCP tools")
    ] = False,
    setup: Annotated[
        bool, typer.Option("--setup", help="Print setup instructions for Claude Code")
    ] = False,
) -> None:
    """Start the SafeClaw MCP server (stdio mode for Claude Code)."""
    from safeclaw.mcp_server import get_setup_instructions, run_server
    from safeclaw.mcp_server import list_tools as get_tools

    if list_tools:
        table = Table(title="SafeClaw MCP Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Description")
        for name, desc in get_tools():
            table.add_row(name, desc)
        console.print(table)
        return

    if setup:
        console.print(get_setup_instructions())
        return

    run_server()
