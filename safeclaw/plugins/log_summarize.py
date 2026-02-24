"""Plugin: summarise log files by extracting error/warning lines."""

from __future__ import annotations

import re
from pathlib import Path

from safeclaw.policy import Policy

_ERROR_RE = re.compile(r"\b(error|exception|failed|traceback)\b", re.IGNORECASE)


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Summarise a log file by pulling out notable lines.

    Args:
        policy: Active security policy.
        target: Path to a log file.

    Returns:
        Summary string and list containing the log file path.
    """
    if not target.is_file():
        return f"Target is not a file: {target}", []

    size_mb = target.stat().st_size / (1024 * 1024)
    if size_mb > policy.limits.max_file_mb:
        return f"File too large ({size_mb:.1f} MB, limit {policy.limits.max_file_mb} MB)", []

    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"Could not read file: {exc}", []

    total = len(lines)
    error_lines: list[str] = []

    for lineno, line in enumerate(lines, start=1):
        if _ERROR_RE.search(line):
            error_lines.append(f"  L{lineno}: {line.strip()}")

    parts: list[str] = [f"Log: {target.name} ({total} lines total)"]

    if error_lines:
        parts.append(f"Found {len(error_lines)} notable line(s):")
        parts.extend(error_lines[:20])
        if len(error_lines) > 20:
            parts.append(f"  ... and {len(error_lines) - 20} more")
    else:
        parts.append("No errors/exceptions/failures detected.")

    return "\n".join(parts), [str(target)]
