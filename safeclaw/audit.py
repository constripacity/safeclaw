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

    _maybe_rotate(audit_path)

    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return audit_path


_MAX_AUDIT_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_ROTATED = 5


def _maybe_rotate(audit_path: Path) -> None:
    """Rotate the audit log if it exceeds the size threshold."""
    if not audit_path.exists():
        return
    try:
        if audit_path.stat().st_size < _MAX_AUDIT_BYTES:
            return
    except OSError:
        return
    rotate_audit(audit_path.parent.parent)


def rotate_audit(project_root: Path | str) -> Path | None:
    """Rotate the audit log file.

    Renames audit.jsonl → audit.jsonl.1, audit.jsonl.1 → audit.jsonl.2, etc.
    Removes the oldest file if it exceeds ``_MAX_ROTATED``.

    Args:
        project_root: Root of the project.

    Returns:
        Path to the rotated file, or None if nothing to rotate.
    """
    audit_path = Path(project_root).resolve() / AUDIT_DIR / AUDIT_FILE
    if not audit_path.exists() or audit_path.stat().st_size == 0:
        return None

    # Shift existing rotated files
    for i in range(_MAX_ROTATED, 0, -1):
        src = audit_path.parent / f"{AUDIT_FILE}.{i}"
        if not src.exists():
            continue
        if i >= _MAX_ROTATED:
            src.unlink()
        else:
            dst = audit_path.parent / f"{AUDIT_FILE}.{i + 1}"
            src.rename(dst)

    # Rotate current file to .1
    rotated = audit_path.parent / f"{AUDIT_FILE}.1"
    audit_path.rename(rotated)
    return rotated


def read_audit(project_root: Path | str, last_n: int = 20) -> list[dict]:
    """Read the most recent *last_n* entries from the audit log.

    Args:
        project_root: Root of the project.
        last_n: How many entries to return (most recent first).

    Returns:
        A list of dicts, newest first.
    """
    if last_n <= 0:
        return []

    audit_path = Path(project_root).resolve() / AUDIT_DIR / AUDIT_FILE
    if not audit_path.exists():
        return []

    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    entries: list[dict] = []
    for line in lines:
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip corrupted lines
    return list(reversed(entries[-last_n:]))
