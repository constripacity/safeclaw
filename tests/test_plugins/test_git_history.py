"""Tests for safeclaw.plugins.git_history."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.plugins.git_history import _count_refs, _parse_reflog, _read_head_ref, run
from safeclaw.policy import Policy


@pytest.fixture()
def policy(tmp_path: Path) -> Policy:
    return Policy(project_root=str(tmp_path), allowed_plugins=["git_history"])


@pytest.fixture()
def fake_git(tmp_path: Path) -> Path:
    """Create a minimal .git directory structure."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    heads = git_dir / "refs" / "heads"
    heads.mkdir(parents=True)
    (heads / "main").write_text("abc123\n", encoding="utf-8")
    (heads / "dev").write_text("def456\n", encoding="utf-8")

    tags = git_dir / "refs" / "tags"
    tags.mkdir(parents=True)
    (tags / "v1.0").write_text("abc123\n", encoding="utf-8")

    logs = git_dir / "logs"
    logs.mkdir()
    reflog_line = (
        "0000000 abc1234 Alice <alice@example.com> 1700000000 +0000\tcommit: initial\n"
        "abc1234 def5678 Bob <bob@example.com> 1700001000 +0000\tcommit: update\n"
        "def5678 aaa9012 Alice <alice@example.com> 1700002000 +0000\tcommit: fix bug\n"
    )
    (logs / "HEAD").write_text(reflog_line, encoding="utf-8")

    return tmp_path


class TestReadHeadRef:
    def test_branch_ref(self, fake_git: Path) -> None:
        ref = _read_head_ref(fake_git / ".git")
        assert ref == "refs/heads/main"

    def test_detached_head(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("abc123def456789\n", encoding="utf-8")
        ref = _read_head_ref(git_dir)
        assert ref == "abc123def456..."

    def test_missing_head(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        assert _read_head_ref(git_dir) is None


class TestCountRefs:
    def test_counts(self, fake_git: Path) -> None:
        counts = _count_refs(fake_git / ".git")
        assert counts["branches"] == 2
        assert counts["tags"] == 1

    def test_no_refs(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        counts = _count_refs(git_dir)
        assert counts["branches"] == 0
        assert counts["tags"] == 0


class TestParseReflog:
    def test_parse_entries(self, fake_git: Path) -> None:
        entries = _parse_reflog(fake_git / ".git")
        assert len(entries) == 3
        assert entries[0]["author"] == "Alice"
        assert entries[0]["action"] == "commit: fix bug"

    def test_missing_reflog(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        assert _parse_reflog(git_dir) == []


class TestGitHistoryRun:
    def test_full_report(self, policy: Policy, fake_git: Path) -> None:
        report, touched = run(policy, fake_git)
        assert "refs/heads/main" in report
        assert "Local branches: 2" in report
        assert "Tags: 1" in report
        assert "Commits in reflog: 3" in report
        assert "Alice" in report
        assert len(touched) >= 1

    def test_no_git_dir(self, policy: Policy, tmp_path: Path) -> None:
        report, touched = run(policy, tmp_path)
        assert "No .git directory" in report
        assert touched == []

    def test_file_target_uses_parent(self, policy: Policy, fake_git: Path) -> None:
        target_file = fake_git / "some_file.py"
        target_file.write_text("pass", encoding="utf-8")
        report, _touched = run(policy, target_file)
        assert "refs/heads/main" in report
