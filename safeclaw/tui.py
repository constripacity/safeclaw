"""SafeClaw Terminal UI -- full-screen Textual app with Scanner, Audit, and Planner tabs."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from safeclaw import __version__
from safeclaw.audit import read_audit
from safeclaw.policy import Policy, load_policy
from safeclaw.runner import RunResult, get_registry, run_plugin

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------

_PLUGIN_DESCRIPTIONS: dict[str, str] = {
    "todo_scan": "Scan for TODO/FIXME/HACK markers",
    "secrets_scan": "Scan for hardcoded secrets",
    "log_summarize": "Summarise a log file",
    "deps_audit": "Audit declared dependencies",
    "repo_stats": "Show repository statistics",
    "license_check": "Check license files",
    "complexity_scan": "Code complexity analysis",
    "git_history": "Analyze git history",
}

_FKEY_PLUGINS = ["todo_scan", "secrets_scan", "repo_stats", "deps_audit", "log_summarize"]


# ---------------------------------------------------------------------------
# Gold / Dark theme CSS
# ---------------------------------------------------------------------------

_APP_CSS = """\
Screen {
    background: #0a0a0a;
}

Header {
    background: #141414;
    color: #d4a843;
    dock: top;
}

Footer {
    background: #141414;
    color: #888888;
}

/* Sidebar */
#sidebar {
    width: 30;
    background: #111111;
    border-right: solid #1a1a1a;
    padding: 1;
}

#sidebar-title {
    color: #d4a843;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
}

ListView {
    background: #111111;
    height: 1fr;
}

ListView > ListItem {
    padding: 0 1;
    height: 3;
    background: #111111;
}

ListView > ListItem:hover {
    background: #1a1a1a;
}

ListView > ListItem.-highlight {
    background: #1f1a0e;
}

ListItem Label {
    padding: 1 1;
}

#target-label {
    color: #888888;
    padding: 1 1 0 1;
}

#target-path {
    margin: 0 1;
    background: #141414;
    border: solid #1a1a1a;
    color: #e0e0e0;
}

#target-path:focus {
    border: solid #d4a843;
}

#btn-run {
    margin: 1 1;
    width: 100%;
    background: #2a2208;
    color: #d4a843;
    border: tall #d4a843;
}

#btn-run:hover {
    background: #3a3010;
    color: #e8c45a;
}

/* Main output */
RichLog {
    background: #0e0e0e;
    border: solid #1a1a1a;
    margin: 0 1;
    scrollbar-background: #141414;
    scrollbar-color: #333333;
}

/* Status bar */
#status-bar {
    height: 3;
    background: #141414;
    border-bottom: solid #1a1a1a;
    padding: 1 2;
    color: #888888;
}

/* Tabs */
TabbedContent {
    background: #0a0a0a;
}

TabPane {
    background: #0a0a0a;
    padding: 0;
}

ContentSwitcher {
    background: #0a0a0a;
}

Tabs {
    background: #141414;
}

Tab {
    background: #141414;
    color: #888888;
    padding: 1 3;
}

Tab:hover {
    color: #d4a843;
    background: #1a1a1a;
}

Tab.-active {
    color: #d4a843;
    background: #0a0a0a;
    text-style: bold;
}

/* Audit DataTable */
DataTable {
    background: #0e0e0e;
    margin: 1;
    scrollbar-background: #141414;
    scrollbar-color: #333333;
}

DataTable > .datatable--header {
    background: #141414;
    color: #d4a843;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1f1a0e;
}

#audit-footer {
    height: 3;
    padding: 1 2;
    color: #888888;
    background: #111111;
}

/* Planner tab */
#planner-input {
    margin: 1 1 0 1;
    background: #141414;
    border: solid #1a1a1a;
    color: #e0e0e0;
}

#planner-input:focus {
    border: solid #d4a843;
}

#planner-buttons {
    height: 3;
    padding: 0 1;
    margin-bottom: 1;
}

#planner-buttons Button {
    margin: 0 1;
    min-width: 12;
}

Button {
    background: #1a1a1a;
    color: #d4a843;
    border: tall #333333;
}

Button:hover {
    background: #2a2208;
    color: #e8c45a;
}

Button.-primary {
    background: #2a2208;
    color: #d4a843;
    border: tall #d4a843;
}

#planner-output {
    background: #0e0e0e;
    border: solid #1a1a1a;
    margin: 0 1;
}

#planner-status {
    height: 3;
    padding: 1 2;
    color: #888888;
    background: #111111;
}
"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class SafeClawTUI(App):
    """SafeClaw interactive terminal UI."""

    TITLE = "SafeClaw"
    SUB_TITLE = "sandboxed dev assistant"
    CSS = _APP_CSS

    BINDINGS = [
        Binding("f1", "run_fkey('todo_scan')", "Todo", show=True),
        Binding("f2", "run_fkey('secrets_scan')", "Secrets", show=True),
        Binding("f3", "run_fkey('repo_stats')", "Stats", show=True),
        Binding("f4", "run_fkey('deps_audit')", "Deps", show=True),
        Binding("f5", "run_fkey('log_summarize')", "Log", show=True),
        Binding("f6", "switch_audit", "Audit", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    policy: reactive[Policy | None] = reactive(None)
    _audit_timer = None
    _current_plan = None

    def __init__(self, policy_path: Path = Path("policy.yaml")) -> None:
        super().__init__()
        self._policy_path = policy_path

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Scanner", "Audit Log", "Planner"):
            # --- Scanner tab ---
            with TabPane("Scanner", id="tab-scanner"):
                yield Static("", id="status-bar")
                with Horizontal():
                    with Vertical(id="sidebar"):
                        yield Label("Plugins", id="sidebar-title")
                        yield ListView(id="plugin-list")
                        yield Label("Target Path", id="target-label")
                        yield Input(value="./", id="target-path")
                        yield Button("Run Scan", variant="primary", id="btn-run")
                    yield RichLog(id="output", highlight=True, markup=True)

            # --- Audit tab ---
            with TabPane("Audit Log", id="tab-audit"):
                yield DataTable(id="audit-table")
                yield Static("", id="audit-footer")

            # --- Planner tab ---
            with TabPane("Planner", id="tab-planner"):
                yield Input(
                    placeholder="Describe your task...",
                    id="planner-input",
                )
                with Horizontal(id="planner-buttons"):
                    yield Button("Plan", variant="primary", id="btn-plan")
                    yield Button("Execute", id="btn-execute")
                    yield Button("Clear", id="btn-clear")
                yield RichLog(id="planner-output", highlight=True, markup=True)
                yield Static("", id="planner-status")

        yield Footer()

    def on_mount(self) -> None:
        """Load policy and populate the UI."""
        try:
            self.policy = load_policy(self._policy_path)
        except (FileNotFoundError, ValueError) as exc:
            self.notify(f"Policy error: {exc}", severity="error", timeout=10)
            return

        self._populate_sidebar()
        self._update_status_bar()
        self._show_welcome()
        self._setup_audit_table()
        self._populate_audit()

        self._audit_timer = self.set_interval(5.0, self._refresh_audit)

    # ----- welcome message -----

    def _show_welcome(self) -> None:
        output = self.query_one("#output", RichLog)
        output.write(Text(f"SafeClaw v{__version__}", style="bold #d4a843"))
        output.write(Text("Ready. Select a plugin and press Enter or click Run Scan.", style="dim"))
        output.write("")

    # ----- sidebar -----

    def _populate_sidebar(self) -> None:
        policy = self.policy
        if not policy:
            return

        plugin_list = self.query_one("#plugin-list", ListView)
        registry = get_registry()

        for name in registry:
            allowed = name in policy.allowed_plugins
            icon = "[green]\u25cf[/green]" if allowed else "[dim]\u25cb[/dim]"
            desc = _PLUGIN_DESCRIPTIONS.get(name, name)
            label = Label(f"{icon} {desc}")
            label.name = name
            item = ListItem(label)
            item.name = name
            plugin_list.append(item)

    # ----- status bar -----

    def _update_status_bar(self) -> None:
        policy = self.policy
        if not policy:
            return

        bar = self.query_one("#status-bar", Static)
        net = "[red]denied[/red]" if not policy.allow_network else "[green]allowed[/green]"
        sh = "[red]denied[/red]" if not policy.allow_shell else "[green]allowed[/green]"
        planner = "[green]on[/green]" if policy.planner.enabled else "[dim]off[/dim]"
        n_active = len(policy.allowed_plugins)
        n_total = len(get_registry())

        bar.update(
            f"[#d4a843]SAFECLAW[/#d4a843] [dim]v{__version__}[/dim] \u2502 "
            f"shell: {sh} \u2502 network: {net} \u2502 "
            f"planner: {planner} \u2502 plugins: {n_active}/{n_total}"
        )

    # ----- plugin execution -----

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle sidebar plugin click."""
        if event.item and event.item.name:
            self._run_selected_plugin(event.item.name)

    def _run_selected_plugin(self, plugin_name: str) -> None:
        """Run a plugin using the target path from the input field."""
        if not self.policy:
            self.notify("No policy loaded", severity="error")
            return
        target = self.query_one("#target-path", Input).value.strip() or "./"
        self._run_plugin_async(plugin_name, target)

    def action_run_fkey(self, plugin_name: str) -> None:
        """Run a plugin via F-key shortcut."""
        self._run_selected_plugin(plugin_name)

    def action_switch_audit(self) -> None:
        """Switch to the Audit Log tab."""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-audit"

    @work(thread=True)
    def _run_plugin_async(self, plugin_name: str, target: str = "./") -> None:
        """Execute plugin in a worker thread."""
        policy = self.policy
        if not policy:
            return

        output = self.query_one("#output", RichLog)
        target_path = Path(target)

        if plugin_name == "log_summarize" and target_path.is_dir():
            sample_log = policy.root_path() / "examples" / "sample-repo" / "build.log"
            if sample_log.exists():
                target_path = sample_log

        output.write(
            Text(
                f"\n\u2500\u2500\u2500 Running {plugin_name} \u2500\u2500\u2500",
                style="bold #d4a843",
            )
        )

        result: RunResult = run_plugin(policy, plugin_name, target_path)

        if result.ok:
            output.write(Text(f"\u2714 {plugin_name} completed", style="bold green"))
        else:
            output.write(Text(f"\u2718 {plugin_name} failed", style="bold red"))

        for line in result.message.split("\n"):
            if any(marker in line.upper() for marker in ("TODO", "FIXME", "HACK")):
                output.write(Text(line, style="yellow"))
            elif any(kw in line.lower() for kw in ("secret", "leak", "exposed")):
                output.write(Text(line, style="red"))
            elif "denied" in line.lower() or "error" in line.lower():
                output.write(Text(line, style="bold red"))
            elif line.startswith("  ") and ":" in line:
                output.write(Text(line, style="cyan"))
            else:
                output.write(line)

        output.write("")

    # ----- audit tab -----

    def _setup_audit_table(self) -> None:
        table = self.query_one("#audit-table", DataTable)
        table.add_columns("Timestamp", "Action", "Status", "Detail")
        table.cursor_type = "row"

    def _populate_audit(self) -> None:
        if not self.policy:
            return
        entries = read_audit(self.policy.root_path(), last_n=50)
        table = self.query_one("#audit-table", DataTable)
        table.clear()

        for entry in entries:
            ts = entry.get("timestamp", "?")[:19]
            action = entry.get("action", "?")
            status = entry.get("status", "?")
            detail = entry.get("detail", "")[:60]

            if status == "ok":
                status_text = Text(status, style="green")
            elif status == "denied":
                status_text = Text(status, style="red bold")
            else:
                status_text = Text(status, style="yellow")

            table.add_row(ts, action, status_text, detail)

        footer = self.query_one("#audit-footer", Static)
        footer.update(f"[dim]Showing {len(entries)} audit entries (refreshes every 5s)[/dim]")

    def _refresh_audit(self) -> None:
        """Called by the interval timer to refresh audit data."""
        tabs = self.query_one(TabbedContent)
        if tabs.active == "tab-audit":
            self._populate_audit()

    # ----- planner tab -----

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run":
            self._do_run_from_button()
        elif event.button.id == "btn-plan":
            self._do_plan()
        elif event.button.id == "btn-execute":
            self._do_execute()
        elif event.button.id == "btn-clear":
            self._do_clear()

    def _do_run_from_button(self) -> None:
        """Run the currently highlighted plugin from the Run Scan button."""
        plugin_list = self.query_one("#plugin-list", ListView)
        if plugin_list.highlighted_child and plugin_list.highlighted_child.name:
            self._run_selected_plugin(plugin_list.highlighted_child.name)
        else:
            self.notify("Select a plugin first", severity="warning")

    @work(thread=True)
    def _do_plan(self) -> None:
        """Generate a plan from the planner input."""
        if not self.policy:
            self.notify("No policy loaded", severity="error")
            return

        task_input = self.query_one("#planner-input", Input)
        task_text = task_input.value.strip()
        if not task_text:
            self.notify("Enter a task description first", severity="warning")
            return

        output = self.query_one("#planner-output", RichLog)
        status = self.query_one("#planner-status", Static)

        output.clear()
        output.write(Text("Generating plan...", style="dim"))
        status.update("[dim]Contacting LLM...[/dim]")

        if not self.policy.planner.enabled:
            output.write(
                Text(
                    "Planner is disabled in policy.yaml.\n"
                    "Set planner.enabled: true to use this feature.",
                    style="red",
                )
            )
            status.update("[red]Planner disabled[/red]")
            return

        try:
            from safeclaw.planner import Planner, PlannerError, validate_plan

            planner = Planner(self.policy)
            plan = planner.plan(task_text)
            result = validate_plan(plan, self.policy)

            output.clear()
            output.write(Text("Generated Plan:", style="bold #d4a843"))
            output.write("")

            rejected_plugins: set[str] = set()
            for rej in result.rejected_steps:
                if "'" in rej:
                    rejected_plugins.add(rej.split("'")[1])

            for i, step in enumerate(plan.steps, 1):
                is_rejected = step.plugin in rejected_plugins
                icon = "\u274c Denied" if is_rejected else "\u2705 Allowed"
                style = "red" if is_rejected else "green"
                output.write(
                    Text(
                        f"  Step {i}: {step.plugin} \u2192 {step.target}  [{icon}]",
                        style=style,
                    )
                )
                if step.reason:
                    output.write(Text(f"          {step.reason}", style="dim"))

            if result.validated:
                status.update(
                    f"[green]Plan ready ({len(plan.steps)} steps) \u2014 press Execute[/green]"
                )
            else:
                for msg in result.rejected_steps:
                    output.write(Text(f"  Rejected: {msg}", style="red"))
                status.update("[red]Plan validation failed[/red]")

            self._current_plan = plan if result.validated else None

        except PlannerError as exc:
            output.clear()
            output.write(Text(f"Planner error: {exc}", style="red"))
            status.update("[red]Plan generation failed[/red]")
            self._current_plan = None

    @work(thread=True)
    def _do_execute(self) -> None:
        """Execute the currently stored plan."""
        if not self.policy:
            self.notify("No policy loaded", severity="error")
            return

        if not self._current_plan:
            self.notify("Generate a plan first", severity="warning")
            return

        from safeclaw.runner import run_plan

        output = self.query_one("#planner-output", RichLog)
        status = self.query_one("#planner-status", Static)

        output.write("")
        output.write(Text("Executing plan...", style="bold #d4a843"))
        status.update("[dim]Running...[/dim]")

        results = run_plan(self.policy, self._current_plan)

        for i, (step, res) in enumerate(zip(self._current_plan.steps, results, strict=False), 1):
            icon = "\u2714" if res.ok else "\u2718"
            style = "green" if res.ok else "red"
            output.write(Text(f"  Step {i} ({step.plugin}): {icon}", style=style))
            if not res.ok:
                output.write(Text(f"    {res.message}", style="dim red"))

        ok = sum(1 for r in results if r.ok)
        status.update(f"[green]{ok}/{len(results)} steps completed[/green]")
        self._current_plan = None

    def _do_clear(self) -> None:
        """Clear the planner view."""
        self.query_one("#planner-input", Input).value = ""
        self.query_one("#planner-output", RichLog).clear()
        self.query_one("#planner-status", Static).update("")
        self._current_plan = None


def run_tui(policy_path: Path = Path("policy.yaml")) -> None:
    """Launch the SafeClaw TUI."""
    app = SafeClawTUI(policy_path=policy_path)
    app.run()
