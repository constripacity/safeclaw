"""Tests for safeclaw.plugins.repo_stats."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.plugins.repo_stats import run
from safeclaw.policy import Limits, Policy


@pytest.fixture()
def stats_policy(tmp_path: Path) -> Policy:
    """Policy rooted at tmp_path with repo_stats allowed."""
    return Policy(
        project_root=str(tmp_path),
        allowed_plugins=["repo_stats"],
    )


class TestRepoStatsRun:
    def test_counts_files_and_lines(self, stats_policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("line1\nline2\nline3\n", encoding="utf-8")
        (tmp_path / "util.py").write_text("a\nb\n", encoding="utf-8")
        msg, touched = run(stats_policy, tmp_path)
        assert "Total files: 2" in msg
        assert "Total lines of code: 5" in msg
        assert ".py" in msg
        assert len(touched) == 2

    def test_empty_directory(self, stats_policy: Policy, tmp_path: Path) -> None:
        msg, touched = run(stats_policy, tmp_path)
        assert "Total files: 0" in msg
        assert "Total lines of code: 0" in msg
        assert touched == []

    def test_binary_files_not_line_counted(self, stats_policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (tmp_path / "code.py").write_text("line1\n", encoding="utf-8")
        msg, touched = run(stats_policy, tmp_path)
        assert "Total files: 2" in msg
        # Only .py lines should be counted, not .png
        assert "Total lines of code: 1" in msg
        assert ".png" in msg

    def test_max_files_limit(self, tmp_path: Path) -> None:
        pol = Policy(
            project_root=str(tmp_path),
            allowed_plugins=["repo_stats"],
            limits=Limits(max_files=3),
        )
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f"# file {i}\n", encoding="utf-8")
        msg, touched = run(pol, tmp_path)
        assert "Total files: 3" in msg
        assert len(touched) == 3

    def test_file_type_distribution(self, stats_policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("y\n", encoding="utf-8")
        (tmp_path / "c.js").write_text("z\n", encoding="utf-8")
        msg, touched = run(stats_policy, tmp_path)
        assert ".py" in msg
        assert ".js" in msg
        assert "Total files: 3" in msg

    def test_target_is_file(self, stats_policy: Policy, tmp_path: Path) -> None:
        """When target is a file, plugin should inspect the parent directory."""
        f = tmp_path / "main.py"
        f.write_text("hello\n", encoding="utf-8")
        msg, touched = run(stats_policy, f)
        assert "Total files: 1" in msg

    def test_subdirectories_counted(self, stats_policy: Policy, tmp_path: Path) -> None:
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "app.py").write_text("a\nb\n", encoding="utf-8")
        (tmp_path / "readme.md").write_text("# readme\n", encoding="utf-8")
        msg, touched = run(stats_policy, tmp_path)
        assert "Total files: 2" in msg
        assert "Total lines of code: 3" in msg

    def test_no_ext_files(self, stats_policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("all:\n\techo hi\n", encoding="utf-8")
        msg, touched = run(stats_policy, tmp_path)
        assert "Total files: 1" in msg
        assert "(no ext)" in msg

    def test_large_file_skipped_for_lines(self, tmp_path: Path) -> None:
        pol = Policy(
            project_root=str(tmp_path),
            allowed_plugins=["repo_stats"],
            limits=Limits(max_file_mb=0),  # 0 MB means skip all files for line counting
        )
        (tmp_path / "big.py").write_text("line\n" * 100, encoding="utf-8")
        msg, touched = run(pol, tmp_path)
        assert "Total files: 1" in msg
        assert "Total lines of code: 0" in msg
