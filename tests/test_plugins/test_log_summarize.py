"""Tests for the log_summarize plugin."""

from pathlib import Path

from safeclaw.plugins.log_summarize import run
from safeclaw.policy import Policy


class TestLogSummarize:
    def test_extracts_error_lines(self, policy: Policy, tmp_project: Path) -> None:
        log = tmp_project / "build.log"
        message, touched = run(policy, log)
        assert "notable line" in message.lower() or "error" in message.lower()
        assert str(log) in touched

    def test_counts_total_lines(self, policy: Policy, tmp_project: Path) -> None:
        log = tmp_project / "build.log"
        message, _ = run(policy, log)
        assert "5 lines" in message

    def test_not_a_file(self, policy: Policy, tmp_project: Path) -> None:
        message, _ = run(policy, tmp_project)
        assert "not a file" in message.lower()

    def test_clean_log(self, tmp_path: Path) -> None:
        log = tmp_path / "clean.log"
        log.write_text("[INFO] All good\n[INFO] Done\n", encoding="utf-8")
        pol = Policy(project_root=str(tmp_path))
        message, _ = run(pol, log)
        assert "No errors" in message

    def test_large_file_rejected(self, tmp_path: Path) -> None:
        """Files exceeding max_file_mb should be rejected."""
        from safeclaw.policy import Limits

        pol = Policy(project_root=str(tmp_path), limits=Limits(max_file_mb=0))
        log = tmp_path / "big.log"
        log.write_text("[ERROR] something\n", encoding="utf-8")
        msg, _ = run(pol, log)
        assert "too large" in msg.lower()

    def test_many_error_lines_truncated(self, tmp_path: Path) -> None:
        """More than 20 error lines should show truncation message."""
        pol = Policy(project_root=str(tmp_path))
        lines = "\n".join(f"[ERROR] error line {i}" for i in range(30))
        log = tmp_path / "errors.log"
        log.write_text(lines, encoding="utf-8")
        msg, _ = run(pol, log)
        assert "... and" in msg
        assert "more" in msg
