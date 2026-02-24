"""Plugin: scan for TODO / FIXME / HACK markers in source files."""

from __future__ import annotations

import re
from pathlib import Path

from safeclaw.policy import Policy

_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)

# File extensions considered "text" for scanning purposes.
_TEXT_EXTENSIONS: set[str] = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sh",
    ".bash",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".xml",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".cfg",
    ".ini",
    ".env",
    ".sql",
    ".r",
    ".kt",
    ".swift",
    ".cs",
}


def _is_scannable(path: Path, max_mb: int) -> bool:
    """Return True if the file should be scanned."""
    if not path.is_file():
        return False
    if path.suffix.lower() not in _TEXT_EXTENSIONS:
        return False
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
        return size_mb <= max_mb
    except OSError:
        return False


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Scan *target* for TODO/FIXME/HACK markers.

    Args:
        policy: Active security policy.
        target: File or directory to scan.

    Returns:
        Formatted results string and list of scanned file paths.
    """
    max_mb = policy.limits.max_file_mb
    max_files = policy.limits.max_files

    files_to_scan: list[Path] = []
    if target.is_file():
        if _is_scannable(target, max_mb):
            files_to_scan.append(target)
    else:
        for p in sorted(target.rglob("*")):
            if len(files_to_scan) >= max_files:
                break
            if _is_scannable(p, max_mb):
                files_to_scan.append(p)

    matches: list[str] = []
    touched: list[str] = []

    for fpath in files_to_scan:
        touched.append(str(fpath))
        try:
            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if _MARKER_RE.search(line):
                rel = fpath.relative_to(target) if target.is_dir() else fpath.name
                matches.append(f"  {rel}:{lineno}: {line.strip()}")

    if matches:
        header = f"Found {len(matches)} marker(s) in {len(files_to_scan)} file(s):\n"
        return header + "\n".join(matches), touched

    return f"No TODO/FIXME/HACK markers found in {len(files_to_scan)} file(s).", touched
