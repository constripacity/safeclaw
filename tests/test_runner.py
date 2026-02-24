"""Tests for safeclaw.runner."""

from pathlib import Path

from safeclaw.policy import Policy
from safeclaw.runner import run_plugin


class TestRunPlugin:
    def test_allowed_plugin_succeeds(self, policy: Policy, tmp_project: Path) -> None:
        result = run_plugin(policy, "todo_scan", tmp_project)
        assert result.ok is True
        assert "TODO" in result.message or "marker" in result.message.lower()

    def test_denied_plugin_blocked(self, policy: Policy, tmp_project: Path) -> None:
        result = run_plugin(policy, "not_allowed_plugin", tmp_project)
        assert result.ok is False
        assert "not in the allowed list" in result.message

    def test_nonexistent_plugin_blocked(self, tmp_project: Path) -> None:
        pol = Policy(
            project_root=str(tmp_project),
            allowed_plugins=["nonexistent_plugin"],
        )
        result = run_plugin(pol, "nonexistent_plugin", tmp_project)
        assert result.ok is False
        assert "not registered" in result.message

    def test_path_outside_root_blocked(self, policy: Policy) -> None:
        outside = Path("/tmp/outside_root_definitely")
        result = run_plugin(policy, "todo_scan", outside)
        assert result.ok is False
        assert "outside project root" in result.message
