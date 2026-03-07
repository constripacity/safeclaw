"""Tests for safeclaw.hooks — pre-commit hook integration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from safeclaw.hooks import (
    HOOK_MARKER_END,
    HOOK_MARKER_START,
    _find_git_dir,
    _remove_safeclaw_section,
    install_hook,
    run_pre_commit_hook,
    uninstall_hook,
)

# ---------------------------------------------------------------------------
# TestFindGitDir
# ---------------------------------------------------------------------------


class TestFindGitDir:
    """Tests for _find_git_dir()."""

    def test_finds_git_in_current_dir(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        assert _find_git_dir(tmp_path) == git_dir

    def test_finds_git_in_parent_dir(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        child = tmp_path / "subdir" / "deep"
        child.mkdir(parents=True)
        assert _find_git_dir(child) == git_dir

    def test_returns_none_when_no_git(self, tmp_path: Path) -> None:
        assert _find_git_dir(tmp_path) is None


# ---------------------------------------------------------------------------
# TestInstallHook
# ---------------------------------------------------------------------------


class TestInstallHook:
    """Tests for install_hook()."""

    def test_creates_hook_when_none_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        hook_path = install_hook(tmp_path)

        assert hook_path.exists()
        content = hook_path.read_text(encoding="utf-8")
        assert content.startswith("#!/bin/sh\n")
        assert HOOK_MARKER_START in content
        assert HOOK_MARKER_END in content
        assert "run_pre_commit_hook" in content

    def test_appends_to_existing_hook(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
        hook_path.write_text("#!/bin/sh\necho 'existing hook'\n", encoding="utf-8")

        install_hook(tmp_path)

        content = hook_path.read_text(encoding="utf-8")
        assert "existing hook" in content
        assert HOOK_MARKER_START in content

    def test_force_replaces_existing_section(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
        hook_path.write_text(
            f"#!/bin/sh\necho 'keep me'\n{HOOK_MARKER_START}\nold stuff\n{HOOK_MARKER_END}\n",
            encoding="utf-8",
        )

        install_hook(tmp_path, force=True)

        content = hook_path.read_text(encoding="utf-8")
        assert "keep me" in content
        assert "old stuff" not in content
        assert HOOK_MARKER_START in content
        assert "run_pre_commit_hook" in content

    def test_raises_when_already_installed_without_force(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
        hook_path.write_text(
            f"#!/bin/sh\n{HOOK_MARKER_START}\nexisting\n{HOOK_MARKER_END}\n",
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError, match="already installed"):
            install_hook(tmp_path)

    def test_raises_when_no_git_dir(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No .git directory"):
            install_hook(tmp_path)

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not supported on Windows")
    def test_sets_executable_permission(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        hook_path = install_hook(tmp_path)

        # Check that the owner execute bit is set
        mode = hook_path.stat().st_mode
        assert mode & 0o100  # S_IXUSR


# ---------------------------------------------------------------------------
# TestUninstallHook
# ---------------------------------------------------------------------------


class TestUninstallHook:
    """Tests for uninstall_hook()."""

    def test_removes_safeclaw_section_leaves_rest(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
        hook_path.write_text(
            f"#!/bin/sh\necho 'keep me'\n{HOOK_MARKER_START}\nsafeclaw stuff\n{HOOK_MARKER_END}\n",
            encoding="utf-8",
        )

        assert uninstall_hook(tmp_path) is True
        content = hook_path.read_text(encoding="utf-8")
        assert "keep me" in content
        assert HOOK_MARKER_START not in content

    def test_returns_false_when_no_safeclaw_section(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
        hook_path.write_text("#!/bin/sh\necho 'other hook'\n", encoding="utf-8")

        assert uninstall_hook(tmp_path) is False

    def test_deletes_empty_hook_file(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
        hook_path.write_text(
            f"#!/bin/sh\n{HOOK_MARKER_START}\nstuff\n{HOOK_MARKER_END}\n",
            encoding="utf-8",
        )

        assert uninstall_hook(tmp_path) is True
        assert not hook_path.exists()

    def test_returns_false_when_no_git_dir(self, tmp_path: Path) -> None:
        assert uninstall_hook(tmp_path) is False

    def test_returns_false_when_no_hook_file(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        assert uninstall_hook(tmp_path) is False


# ---------------------------------------------------------------------------
# TestRemoveSafeClawSection
# ---------------------------------------------------------------------------


class TestRemoveSafeClawSection:
    """Tests for _remove_safeclaw_section()."""

    def test_removes_section(self) -> None:
        content = f"before\n{HOOK_MARKER_START}\nmiddle\n{HOOK_MARKER_END}\nafter\n"
        result = _remove_safeclaw_section(content)
        assert "before" in result
        assert "after" in result
        assert "middle" not in result

    def test_no_section_returns_unchanged(self) -> None:
        content = "just a normal hook\n"
        assert _remove_safeclaw_section(content) == content


# ---------------------------------------------------------------------------
# TestRunPreCommitHook
# ---------------------------------------------------------------------------


class TestRunPreCommitHook:
    """Tests for run_pre_commit_hook()."""

    def test_no_staged_files_returns_zero(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("safeclaw.hooks.subprocess.run", return_value=mock_result):
            assert run_pre_commit_hook(str(tmp_path / "policy.yaml")) == 0

    def test_clean_staged_file_returns_zero(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            f"project_root: '{tmp_path}'\nallowed_plugins: [secrets_scan]\n",
            encoding="utf-8",
        )

        clean_file = tmp_path / "clean.py"
        clean_file.write_text("x = 1\n", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.stdout = "clean.py\n"

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("safeclaw.hooks.subprocess.run", return_value=mock_result):
                assert run_pre_commit_hook(str(policy_file)) == 0
        finally:
            os.chdir(old_cwd)

    def test_staged_file_with_secret_returns_one(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            f"project_root: '{tmp_path}'\nallowed_plugins: [secrets_scan]\n",
            encoding="utf-8",
        )

        secret_file = tmp_path / "config.py"
        secret_file.write_text(
            'AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n',
            encoding="utf-8",
        )

        mock_result = MagicMock()
        mock_result.stdout = "config.py\n"

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch("safeclaw.hooks.subprocess.run", return_value=mock_result):
                assert run_pre_commit_hook(str(policy_file)) == 1
        finally:
            os.chdir(old_cwd)

    def test_git_command_failure_returns_one(self) -> None:
        with patch(
            "safeclaw.hooks.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            assert run_pre_commit_hook("policy.yaml") == 1

    def test_secrets_scan_not_in_policy_returns_zero(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            f"project_root: '{tmp_path}'\nallowed_plugins: [todo_scan]\n",
            encoding="utf-8",
        )

        mock_result = MagicMock()
        mock_result.stdout = "some_file.py\n"

        with patch("safeclaw.hooks.subprocess.run", return_value=mock_result):
            assert run_pre_commit_hook(str(policy_file)) == 0


# ---------------------------------------------------------------------------
# TestCliCommands
# ---------------------------------------------------------------------------


class TestCliCommands:
    """Tests for init/deinit CLI commands."""

    def test_init_installs_hook(self, tmp_path: Path) -> None:
        from safeclaw.cli import app

        runner = CliRunner()
        (tmp_path / ".git").mkdir()
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            f"project_root: '{tmp_path}'\nallowed_plugins: [secrets_scan]\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["init", "--policy", str(policy_file)])
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    def test_init_no_git_exits_one(self, tmp_path: Path) -> None:
        from safeclaw.cli import app

        runner = CliRunner()
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            f"project_root: '{tmp_path}'\nallowed_plugins: [secrets_scan]\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["init", "--policy", str(policy_file)])
        assert result.exit_code == 1
        assert "No .git directory" in result.output

    def test_deinit_no_hook(self, tmp_path: Path) -> None:
        from safeclaw.cli import app

        runner = CliRunner()
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            f"project_root: '{tmp_path}'\nallowed_plugins: [secrets_scan]\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["deinit", "--policy", str(policy_file)])
        assert result.exit_code == 0
        assert "No SafeClaw hook found" in result.output
