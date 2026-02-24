"""Append-only JSONL audit log with automatic secret redaction."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from safeclaw.redaction import redact

AUDIT_DIR = ".safeclaw"
AUDIT_FILE = "audit.jsonl"


@dataclass
class AuditEvent:
    """A single audit log entry."""

    action: str
    status: str
    detail: str = ""
    touched_files: list[str] = field(default_factory=list)


def write_audit(project_root: Path | str, event: AuditEvent) -> Path:
    """Append an audit event to the project's audit log.

    The detail field is passed through ``redact()`` before writing.
    A UTC ISO-8601 timestamp is added automatically.

    Args:
        project_root: Root of the project being scanned.
        event: The event to record.

    Returns:
        Path to the audit log file.
    """
    root = Path(project_root).resolve()
    audit_dir = root / AUDIT_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / AUDIT_FILE

    record = asdict(event)
    record["detail"] = redact(record["detail"])
    record["timestamp"] = datetime.now(UTC).isoformat()

    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return audit_path


def read_audit(project_root: Path | str, last_n: int = 20) -> list[dict]:
    """Read the most recent *last_n* entries from the audit log.

    Args:
        project_root: Root of the project.
        last_n: How many entries to return (most recent first).

    Returns:
        A list of dicts, newest first.
    """
    audit_path = Path(project_root).resolve() / AUDIT_DIR / AUDIT_FILE
    if not audit_path.exists():
        return []

    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return list(reversed(entries[-last_n:]))
