"""Tests for safeclaw.audit."""

import json
from pathlib import Path

from safeclaw.audit import AuditEvent, read_audit, write_audit


class TestAudit:
    def test_creates_audit_file(self, tmp_path: Path) -> None:
        event = AuditEvent(action="test", status="ok", detail="hello")
        audit_path = write_audit(tmp_path, event)
        assert audit_path.exists()

    def test_audit_entry_has_timestamp(self, tmp_path: Path) -> None:
        write_audit(tmp_path, AuditEvent(action="test", status="ok"))
        entries = read_audit(tmp_path, last_n=1)
        assert len(entries) == 1
        assert "timestamp" in entries[0]

    def test_redaction_in_audit(self, tmp_path: Path) -> None:
        secret = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        write_audit(tmp_path, AuditEvent(action="test", status="ok", detail=secret))
        audit_path = tmp_path / ".safeclaw" / "audit.jsonl"
        content = audit_path.read_text(encoding="utf-8")
        record = json.loads(content.strip())
        assert secret not in record["detail"]
        assert "[REDACTED:" in record["detail"]

    def test_read_audit_empty(self, tmp_path: Path) -> None:
        entries = read_audit(tmp_path)
        assert entries == []

    def test_read_audit_ordering(self, tmp_path: Path) -> None:
        for i in range(5):
            write_audit(tmp_path, AuditEvent(action=f"step{i}", status="ok"))
        entries = read_audit(tmp_path, last_n=3)
        assert len(entries) == 3
        # Most recent first
        assert entries[0]["action"] == "step4"
        assert entries[2]["action"] == "step2"

    def test_touched_files_recorded(self, tmp_path: Path) -> None:
        write_audit(
            tmp_path,
            AuditEvent(action="scan", status="ok", touched_files=["a.py", "b.py"]),
        )
        entries = read_audit(tmp_path, last_n=1)
        assert entries[0]["touched_files"] == ["a.py", "b.py"]
