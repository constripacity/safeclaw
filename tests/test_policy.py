"""Tests for safeclaw.policy."""

from pathlib import Path

import pytest

from safeclaw.policy import DashboardConfig, PlannerConfig, Policy, load_policy


class TestPolicyModel:
    def test_defaults(self) -> None:
        p = Policy()
        assert p.allow_network is False
        assert p.allow_shell is False
        assert p.allowed_plugins == []
        assert p.limits.max_file_mb == 5

    def test_root_path_resolves(self) -> None:
        p = Policy(project_root=".")
        assert p.root_path().is_absolute()

    def test_sandbox_path(self, tmp_path: Path) -> None:
        p = Policy(project_root=str(tmp_path), sandbox_subdir="sandbox")
        assert p.sandbox_path() == tmp_path / "sandbox"

    def test_deduplicates_plugins(self) -> None:
        p = Policy(allowed_plugins=["a", "b", "a"])
        assert p.allowed_plugins == ["a", "b"]

    def test_planner_defaults(self) -> None:
        p = Policy()
        assert p.planner.enabled is False
        assert p.planner.backend == "ollama"
        assert p.planner.max_steps == 5
        assert p.planner.require_confirmation is True
        assert p.planner.api_key_env == ""

    def test_dashboard_defaults(self) -> None:
        p = Policy()
        assert p.dashboard.enabled is False
        assert p.dashboard.host == "127.0.0.1"
        assert p.dashboard.port == 8321

    def test_planner_config_override(self) -> None:
        p = Policy(planner=PlannerConfig(enabled=True, backend="openai", model="gpt-4o-mini"))
        assert p.planner.enabled is True
        assert p.planner.backend == "openai"
        assert p.planner.model == "gpt-4o-mini"

    def test_dashboard_config_override(self) -> None:
        p = Policy(dashboard=DashboardConfig(enabled=True, port=9000))
        assert p.dashboard.enabled is True
        assert p.dashboard.port == 9000


class TestLoadPolicy:
    def test_load_valid_policy(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            "project_root: .\nallow_network: false\nallowed_plugins:\n  - todo_scan\n",
            encoding="utf-8",
        )
        p = load_policy(policy_file)
        assert p.allow_network is False
        assert "todo_scan" in p.allowed_plugins

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_policy("/nonexistent/policy.yaml")

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_policy(policy_file)

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("just a string", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_policy(policy_file)

    def test_load_without_planner_section(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("project_root: .\n", encoding="utf-8")
        p = load_policy(policy_file)
        assert p.planner.enabled is False
        assert p.dashboard.enabled is False

    def test_load_with_planner_section(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            "project_root: .\nplanner:\n  enabled: true\n  backend: openai\n",
            encoding="utf-8",
        )
        p = load_policy(policy_file)
        assert p.planner.enabled is True
        assert p.planner.backend == "openai"

    def test_load_with_dashboard_section(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            "project_root: .\ndashboard:\n  enabled: true\n  port: 9999\n",
            encoding="utf-8",
        )
        p = load_policy(policy_file)
        assert p.dashboard.enabled is True
        assert p.dashboard.port == 9999
