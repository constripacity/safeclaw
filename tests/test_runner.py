"""Tests for safeclaw.runner."""

from pathlib import Path

import pytest

from safeclaw.planner import ExecutionPlan, PlanStep
from safeclaw.policy import Policy
from safeclaw.runner import get_registry, run_plan, run_plugin


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

    def test_plugin_exception_returns_error(
        self, tmp_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If a plugin raises, run_plugin returns ok=False with the exception message."""
        from safeclaw.runner import _PLUGIN_REGISTRY, _register_builtins

        _register_builtins()

        def bad_plugin(policy: Policy, target: Path) -> tuple[str, list[str]]:
            raise RuntimeError("boom")

        monkeypatch.setitem(_PLUGIN_REGISTRY, "todo_scan", bad_plugin)
        pol = Policy(project_root=str(tmp_project), allowed_plugins=["todo_scan"])
        result = run_plugin(pol, "todo_scan", tmp_project)
        assert result.ok is False
        assert "exception" in result.message.lower()
        assert "boom" in result.message

    def test_string_target_path(self, policy: Policy, tmp_project: Path) -> None:
        """run_plugin accepts string target paths."""
        result = run_plugin(policy, "todo_scan", str(tmp_project))
        assert result.ok is True


class TestGetRegistry:
    def test_registry_contains_all_builtins(self) -> None:
        registry = get_registry()
        expected = {
            "todo_scan",
            "log_summarize",
            "secrets_scan",
            "deps_audit",
            "repo_stats",
            "license_check",
            "complexity_scan",
            "git_history",
        }
        assert expected == set(registry.keys())

    def test_registry_values_are_callable(self) -> None:
        registry = get_registry()
        for fn in registry.values():
            assert callable(fn)


class TestRunPlan:
    def test_empty_plan(self, policy: Policy) -> None:
        plan = ExecutionPlan(steps=[])
        results = run_plan(policy, plan)
        assert results == []

    def test_single_step_succeeds(self, policy: Policy, tmp_project: Path) -> None:
        plan = ExecutionPlan(
            steps=[PlanStep(plugin="repo_stats", target=str(tmp_project), reason="stats")]
        )
        results = run_plan(policy, plan)
        assert len(results) == 1
        assert results[0].ok is True

    def test_multiple_steps_succeed(self, policy: Policy, tmp_project: Path) -> None:
        plan = ExecutionPlan(
            steps=[
                PlanStep(plugin="todo_scan", target=str(tmp_project), reason="scan"),
                PlanStep(plugin="repo_stats", target=str(tmp_project), reason="stats"),
            ]
        )
        results = run_plan(policy, plan)
        assert len(results) == 2
        assert all(r.ok for r in results)

    def test_fail_fast_on_denied_plugin(self, policy: Policy, tmp_project: Path) -> None:
        """run_plan stops after the first failure."""
        plan = ExecutionPlan(
            steps=[
                PlanStep(plugin="not_allowed", target=str(tmp_project), reason="bad"),
                PlanStep(plugin="todo_scan", target=str(tmp_project), reason="scan"),
            ]
        )
        results = run_plan(policy, plan)
        assert len(results) == 1
        assert results[0].ok is False
