"""Tests for the todo_scan plugin."""

from pathlib import Path

from safeclaw.plugins.todo_scan import run
from safeclaw.policy import Policy


class TestTodoScan:
    def test_finds_todo_markers(self, policy: Policy, tmp_project: Path) -> None:
        message, touched = run(policy, tmp_project)
        assert "TODO" in message
        assert "FIXME" in message

    def test_reports_line_numbers(self, policy: Policy, tmp_project: Path) -> None:
        message, _ = run(policy, tmp_project)
        # Format: file:lineno: content
        assert ":1:" in message or ":2:" in message

    def test_no_markers_clean_file(self, tmp_path: Path) -> None:
        clean = tmp_path / "clean.py"
        clean.write_text("def hello():\n    return 42\n", encoding="utf-8")
        pol = Policy(project_root=str(tmp_path))
        message, _ = run(pol, tmp_path)
        assert "No TODO" in message

    def test_single_file_mode(self, policy: Policy, tmp_project: Path) -> None:
        target = tmp_project / "app.py"
        message, touched = run(policy, target)
        assert "TODO" in message
        assert len(touched) == 1
