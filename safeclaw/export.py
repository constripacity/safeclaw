"""Audit log export — CSV, JSON, and HTML format handlers."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from safeclaw.audit import read_audit
from safeclaw.policy import Policy

_FIELDS = ["timestamp", "action", "status", "detail", "touched_files"]


def export_csv(entries: list[dict[str, Any]]) -> str:
    """Format audit entries as CSV text.

    Args:
        entries: List of audit entry dicts.

    Returns:
        CSV-formatted string with header row.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for entry in entries:
        row = dict(entry)
        row["touched_files"] = ";".join(row.get("touched_files", []))
        writer.writerow(row)
    return output.getvalue()


def export_json(entries: list[dict[str, Any]]) -> str:
    """Format audit entries as pretty-printed JSON array.

    Args:
        entries: List of audit entry dicts.

    Returns:
        JSON-formatted string.
    """
    return json.dumps(entries, indent=2, ensure_ascii=False)


def export_html(entries: list[dict[str, Any]]) -> str:
    """Format audit entries as a standalone HTML table.

    Args:
        entries: List of audit entry dicts.

    Returns:
        HTML string with embedded CSS.
    """
    rows = ""
    for e in entries:
        ts = _esc(e.get("timestamp", "?")[:19])
        action = _esc(e.get("action", "?"))
        status = e.get("status", "?")
        detail = _esc(e.get("detail", ""))
        files = _esc(", ".join(e.get("touched_files", [])))
        cls = "ok" if status == "ok" else "error"
        rows += (
            f"<tr><td>{ts}</td><td>{action}</td>"
            f'<td class="{cls}">{_esc(status)}</td>'
            f"<td>{detail}</td><td>{files}</td></tr>\n"
        )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>SafeClaw Audit Export</title>"
        "<style>"
        "body{font-family:sans-serif;background:#1a1a2e;color:#e0e0e0;padding:24px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{padding:8px 12px;border-bottom:1px solid #333;text-align:left;}"
        "th{background:#16213e;}"
        ".ok{color:#4ecca3;}.error{color:#e94560;}"
        "</style></head><body>"
        "<h1>SafeClaw Audit Export</h1>"
        "<table><tr><th>Timestamp</th><th>Action</th><th>Status</th>"
        "<th>Detail</th><th>Files</th></tr>\n"
        f"{rows}</table></body></html>"
    )


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_FORMATTERS: dict[str, Any] = {
    "csv": export_csv,
    "json": export_json,
    "html": export_html,
}


def export_audit(
    policy: Policy,
    *,
    fmt: str = "json",
    count: int = 50,
    output_path: Path | None = None,
) -> str:
    """Export audit log entries in the specified format.

    Args:
        policy: Active policy (used to find project root).
        fmt: Output format — "csv", "json", or "html".
        count: Number of recent entries to export.
        output_path: If provided, write output to this file.

    Returns:
        The formatted output string.

    Raises:
        ValueError: If fmt is not a recognized format.
    """
    if fmt not in _FORMATTERS:
        msg = f"Unknown export format: {fmt!r}. Choose from: {', '.join(_FORMATTERS)}"
        raise ValueError(msg)

    entries = read_audit(policy.root_path(), last_n=count)
    result = _FORMATTERS[fmt](entries)

    if output_path is not None:
        output_path.write_text(result, encoding="utf-8")

    return result
