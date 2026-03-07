"""Tests for safeclaw.cli — Typer CLI commands via CliRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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

    def test_plan_without_dry_run_planner_disabled(self, sample_project: Path) -> None:
        """Plan command without --dry-run also fails when planner is disabled."""
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["plan", "scan for issues", "--policy", policy_path])
        assert result.exit_code == 1


class TestCliDashboard:
    def test_dashboard_disabled_exits_with_error(self, sample_project: Path) -> None:
        """Dashboard command should fail if dashboard is disabled in policy."""
        policy_path = str(sample_project / "policy.yaml")
        result = runner.invoke(app, ["dashboard", "--policy", policy_path])
        assert result.exit_code == 1
        assert "disabled" in result.output.lower()


class TestCliRunAndDisplay:
    def test_denied_plugin_exits_code_1(self, sample_project: Path) -> None:
        """Running a plugin not in the allowlist should exit with code 1."""
        policy_path = str(sample_project / "policy.yaml")
        # Remove all allowed plugins to make todo_scan denied
        policy_yaml = sample_project / "policy.yaml"
        policy_yaml.write_text(
            "project_root: " + str(sample_project).replace("\\", "/") + "\nallowed_plugins: []\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["todo", str(sample_project), "--policy", policy_path])
        assert result.exit_code == 1
        assert "not in the allowed list" in result.output


class TestCliPlanExecution:
    def test_plan_dry_run_with_enabled_planner(self, sample_project: Path) -> None:
        """Plan --dry-run with enabled planner shows plan without executing."""
        policy_path = str(sample_project / "policy.yaml")
        policy_yaml = sample_project / "policy.yaml"
        policy_yaml.write_text(
            "project_root: " + str(sample_project).replace("\\", "/") + "\n"
            "allowed_plugins:\n"
            "  - todo_scan\n"
            "  - secrets_scan\n"
            "planner:\n"
            "  enabled: true\n"
            "  backend: ollama\n"
            "  base_url: http://localhost:11434\n",
            encoding="utf-8",
        )

        mock_response = '{"steps": [{"plugin": "todo_scan", "target": "./", "reason": "scan"}]}'

        from safeclaw.planner import _OllamaBackend

        with patch.object(_OllamaBackend, "call", return_value=mock_response):
            result = runner.invoke(
                app,
                ["plan", "scan for issues", "--dry-run", "--policy", policy_path],
            )
        assert result.exit_code == 0
        assert "todo_scan" in result.output
        assert "Dry run" in result.output

    def test_plan_with_rejected_steps(self, sample_project: Path) -> None:
        """Plan with disallowed plugins shows rejection."""
        policy_path = str(sample_project / "policy.yaml")
        policy_yaml = sample_project / "policy.yaml"
        policy_yaml.write_text(
            "project_root: " + str(sample_project).replace("\\", "/") + "\n"
            "allowed_plugins:\n"
            "  - todo_scan\n"
            "planner:\n"
            "  enabled: true\n"
            "  backend: ollama\n"
            "  base_url: http://localhost:11434\n",
            encoding="utf-8",
        )

        mock_response = '{"steps": [{"plugin": "evil_plugin", "target": "./", "reason": "hack"}]}'

        from safeclaw.planner import _OllamaBackend

        with patch.object(_OllamaBackend, "call", return_value=mock_response):
            result = runner.invoke(
                app,
                ["plan", "do something bad", "--dry-run", "--policy", policy_path],
            )
        assert result.exit_code == 1
        assert "validation failed" in result.output.lower() or "Rejected" in result.output

    def test_plan_execute_auto_with_confirmation_required(self, sample_project: Path) -> None:
        """--auto with require_confirmation should fail."""
        policy_path = str(sample_project / "policy.yaml")
        policy_yaml = sample_project / "policy.yaml"
        policy_yaml.write_text(
            "project_root: " + str(sample_project).replace("\\", "/") + "\n"
            "allowed_plugins:\n"
            "  - todo_scan\n"
            "planner:\n"
            "  enabled: true\n"
            "  backend: ollama\n"
            "  base_url: http://localhost:11434\n"
            "  require_confirmation: true\n",
            encoding="utf-8",
        )

        mock_response = '{"steps": [{"plugin": "todo_scan", "target": "./", "reason": "scan"}]}'

        from safeclaw.planner import _OllamaBackend

        with patch.object(_OllamaBackend, "call", return_value=mock_response):
            result = runner.invoke(
                app,
                ["plan", "scan", "--auto", "--policy", policy_path],
            )
        assert result.exit_code == 1

    def test_plan_connection_error(self, sample_project: Path) -> None:
        """Plan with connection error should show error message."""
        policy_path = str(sample_project / "policy.yaml")
        policy_yaml = sample_project / "policy.yaml"
        policy_yaml.write_text(
            "project_root: " + str(sample_project).replace("\\", "/") + "\n"
            "allowed_plugins:\n"
            "  - todo_scan\n"
            "planner:\n"
            "  enabled: true\n"
            "  backend: ollama\n"
            "  base_url: http://localhost:11434\n",
            encoding="utf-8",
        )

        from safeclaw.planner import PlanConnectionError, _OllamaBackend

        def mock_call(self, policy, system, user_msg):
            raise PlanConnectionError("Ollama not running")

        with patch.object(_OllamaBackend, "call", mock_call):
            result = runner.invoke(
                app,
                ["plan", "scan", "--policy", policy_path],
            )
        assert result.exit_code == 1
        assert "Connection error" in result.output or "not running" in result.output

    def test_plan_parse_error(self, sample_project: Path) -> None:
        """Plan with parse error should show raw response."""
        policy_path = str(sample_project / "policy.yaml")
        policy_yaml = sample_project / "policy.yaml"
        policy_yaml.write_text(
            "project_root: " + str(sample_project).replace("\\", "/") + "\n"
            "allowed_plugins:\n"
            "  - todo_scan\n"
            "planner:\n"
            "  enabled: true\n"
            "  backend: ollama\n"
            "  base_url: http://localhost:11434\n",
            encoding="utf-8",
        )

        from safeclaw.planner import _OllamaBackend

        with patch.object(_OllamaBackend, "call", return_value="I cannot do that"):
            result = runner.invoke(
                app,
                ["plan", "scan", "--policy", policy_path],
            )
        assert result.exit_code == 1
        assert "parse" in result.output.lower() or "Failed" in result.output


class TestCliBanner:
    def test_no_args_shows_banner(self) -> None:
        """Running safeclaw with no args shows the welcome banner."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "safeclaw" in result.output.lower()

    def test_version_flag(self) -> None:
        """--version prints version and exits."""
        from safeclaw import __version__

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
