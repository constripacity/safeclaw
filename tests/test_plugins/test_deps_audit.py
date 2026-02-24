"""Tests for safeclaw.plugins.deps_audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.plugins.deps_audit import (
    _parse_pyproject_toml,
    _parse_requirements_txt,
    run,
)
from safeclaw.policy import Policy


@pytest.fixture()
def deps_policy(tmp_path: Path) -> Policy:
    """Policy rooted at tmp_path with deps_audit allowed."""
    return Policy(
        project_root=str(tmp_path),
        allowed_plugins=["deps_audit"],
    )


class TestParseRequirementsTxt:
    def test_simple_requirements(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.31.0\nflask==3.0.0\n", encoding="utf-8")
        deps = _parse_requirements_txt(req)
        assert len(deps) == 2
        assert deps[0] == ("requests", ">=2.31.0")
        assert deps[1] == ("flask", "==3.0.0")

    def test_comments_and_blanks_skipped(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text(
            "# This is a comment\n\nrequests>=2.0\n-e ./local_pkg\n",
            encoding="utf-8",
        )
        deps = _parse_requirements_txt(req)
        assert len(deps) == 1
        assert deps[0][0] == "requests"

    def test_empty_file(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("", encoding="utf-8")
        deps = _parse_requirements_txt(req)
        assert deps == []

    def test_no_specifier(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("requests\n", encoding="utf-8")
        deps = _parse_requirements_txt(req)
        assert len(deps) == 1
        assert deps[0] == ("requests", "")


class TestParsePyprojectToml:
    def test_simple_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test"\n'
            "dependencies = [\n"
            '    "typer>=0.12.0",\n'
            '    "pydantic>=2.7.0",\n'
            "]\n",
            encoding="utf-8",
        )
        deps = _parse_pyproject_toml(pyproject)
        assert len(deps) == 2
        assert deps[0][0] == "typer"
        assert deps[1][0] == "pydantic"

    def test_no_dependencies_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n', encoding="utf-8")
        deps = _parse_pyproject_toml(pyproject)
        assert deps == []

    def test_empty_dependencies(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\ndependencies = [\n]\n",
            encoding="utf-8",
        )
        deps = _parse_pyproject_toml(pyproject)
        assert deps == []


class TestDepsAuditRun:
    def test_with_pyproject_deps(self, deps_policy: Policy, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\ndependencies = [\n    "requests>=2.31.0",\n    "flask>=3.0.0",\n]\n',
            encoding="utf-8",
        )
        msg, touched = run(deps_policy, tmp_path)
        assert "2 declared dependency" in msg
        assert "requests" in msg
        assert "flask" in msg
        assert any("pyproject.toml" in t for t in touched)

    def test_with_requirements_txt(self, deps_policy: Policy, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("django>=4.2\ncelery>=5.3\n", encoding="utf-8")
        msg, touched = run(deps_policy, tmp_path)
        assert "2 declared dependency" in msg
        assert "django" in msg
        assert any("requirements.txt" in t for t in touched)

    def test_no_dependency_files(self, tmp_path: Path) -> None:
        pol = Policy(project_root=str(tmp_path), allowed_plugins=["deps_audit"])
        msg, touched = run(pol, tmp_path)
        assert "No dependency files found" in msg

    def test_empty_dependency_file(self, deps_policy: Policy, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("# only comments\n", encoding="utf-8")
        msg, touched = run(deps_policy, tmp_path)
        assert "No dependency files found" in msg

    def test_pinned_zero_version_warning(self, deps_policy: Policy, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("old-lib==0.1.2\n", encoding="utf-8")
        msg, touched = run(deps_policy, tmp_path)
        assert "pinned to 0.x" in msg
        assert "Warning" in msg

    def test_target_is_file(self, deps_policy: Policy, tmp_path: Path) -> None:
        """When target is a file, plugin should inspect the parent directory."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\ndependencies = [\n    "requests>=2.0",\n]\n',
            encoding="utf-8",
        )
        msg, touched = run(deps_policy, pyproject)
        assert "1 declared dependency" in msg

    def test_both_files_combined(self, deps_policy: Policy, tmp_path: Path) -> None:
        """Both requirements.txt and pyproject.toml deps are combined."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.0\n", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\ndependencies = [\n    "flask>=3.0",\n]\n',
            encoding="utf-8",
        )
        msg, touched = run(deps_policy, tmp_path)
        assert "2 declared dependency" in msg
        assert len(touched) == 2
