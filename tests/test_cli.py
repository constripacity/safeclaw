"""Tests for safeclaw.cli — Typer CLI commands via CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from safeclaw.cli import app

runner = CliRunner()


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal sample project for CLI tests."""
    (tmp_path / "app.py").write_text(
        "# TODO: fix this\n"
        'API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"\n'
        "def hello():\n"
        '    return "world"\n',
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-placeholder1234567890abcdefghijklmnop\n",
        encoding="utf-8",
    )
    (tmp_path / "build.log").write_text(
        "[INFO] Starting build\n[ERROR] Failed to compile module\n[INFO] Build complete\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\ndependencies = [\n    "requests>=2.0",\n]\n',
        encoding="utf-8",
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "project_root: " + str(tmp_path).replace("\\", "/") + "\n"
        "allowed_plugins:\n"
        "  - todo_scan\n"
        "  - secrets_scan\n"
        "  - log_summarize\n"
        "  - deps_audit\n"
        "  - repo_stats\n",
        encoding="utf-8",
    )
    return tmp_path


class TestCliTodo:
    def test_todo_scan(self, sample_project: Path) -> None:
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["todo", str(sample_project), "--policy", policy_path])
        assert result.exit_code == 0
        assert "TODO" in result.output

    def test_todo_no_markers(self, sample_project: Path) -> None:
        (sample_project / "app.py").write_text("def clean():\n    pass\n", encoding="utf-8")
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["todo", str(sample_project), "--policy", policy_path])
        assert result.exit_code == 0


class TestCliSecrets:
    def test_secrets_scan(self, sample_project: Path) -> None:
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["secrets", str(sample_project), "--policy", policy_path])
        assert result.exit_code == 0
        assert "secret" in result.output.lower() or "OPENAI" in result.output


class TestCliSummarize:
    def test_summarize_log(self, sample_project: Path) -> None:
        log_path = str(sample_project / "build.log")
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["summarize", log_path, "--policy", policy_path])
        assert result.exit_code == 0
        assert "ERROR" in result.output or "notable" in result.output.lower()


class TestCliDeps:
    def test_deps_audit(self, sample_project: Path) -> None:
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["deps", str(sample_project), "--policy", policy_path])
        assert result.exit_code == 0
        assert "requests" in result.output


class TestCliStats:
    def test_stats(self, sample_project: Path) -> None:
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["stats", str(sample_project), "--policy", policy_path])
        assert result.exit_code == 0
        assert "Total files" in result.output


class TestCliPolicy:
    def test_policy_display(self, sample_project: Path) -> None:
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["policy", "--policy", policy_path])
        assert result.exit_code == 0
        assert "todo_scan" in result.output


class TestCliAudit:
    def test_audit_empty(self, sample_project: Path) -> None:
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["audit", "--policy", policy_path])
        assert result.exit_code == 0

    def test_audit_after_run(self, sample_project: Path) -> None:
        """Audit log should have entries after running a command."""
        policy_path = str(sample_project / "policy.yaml")
        runner.invoke(app, ["todo", str(sample_project), "--policy", policy_path])
        result = runner.invoke(app, ["audit", "--policy", policy_path])
        assert result.exit_code == 0
        assert "todo_scan" in result.output


class TestCliPlan:
    def test_plan_dry_run_planner_disabled(self, sample_project: Path) -> None:
        """Plan command should fail gracefully when planner is disabled."""
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(
            app, ["plan", "scan for issues", "--dry-run", "--policy", policy_path]
        )
        assert result.exit_code == 1
        assert "disabled" in result.output.lower() or "Planner" in result.output
