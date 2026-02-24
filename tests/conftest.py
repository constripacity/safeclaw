"""Shared test fixtures for SafeClaw."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.policy import Policy


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal temporary project directory."""
    # Python file with TODO markers and a fake secret
    py_file = tmp_path / "app.py"
    py_file.write_text(
        "# TODO: fix this\n"
        "# FIXME: broken\n"
        'API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"\n'
        "def hello():\n"
        '    return "world"\n',
        encoding="utf-8",
    )

    # .env file with fake credentials
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=sk-placeholder1234567890abcdefghijklmnop\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n",
        encoding="utf-8",
    )

    # Sample build log
    log_file = tmp_path / "build.log"
    log_file.write_text(
        "[INFO] Starting build\n"
        "[ERROR] Failed to compile module\n"
        "[INFO] Retrying...\n"
        "[ERROR] Traceback (most recent call last):\n"
        "[INFO] Build complete\n",
        encoding="utf-8",
    )

    # pyproject.toml with dependencies
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\n"
        'name = "test-project"\n'
        "dependencies = [\n"
        '    "requests>=2.31.0",\n'
        '    "flask>=3.0.0",\n'
        "]\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def policy(tmp_project: Path) -> Policy:
    """Return a Policy rooted at the temporary project."""
    return Policy(
        project_root=str(tmp_project),
        allowed_plugins=[
            "todo_scan",
            "log_summarize",
            "secrets_scan",
            "deps_audit",
            "repo_stats",
        ],
    )
