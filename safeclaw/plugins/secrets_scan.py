"""Plugin: detect hardcoded secrets in project files."""

from __future__ import annotations

from pathlib import Path

from safeclaw.policy import Policy
from safeclaw.redaction import get_patterns

# File extensions to scan for secrets.
_SCANNABLE_EXTS: set[str] = {
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".log",
    ".toml",
    ".cfg",
    ".ini",
    ".sh",
    ".bash",
    ".js",
    ".ts",
}

# Dotfiles matched by full name (Path.suffix is empty for these).
_SCANNABLE_NAMES: set[str] = {".env", ".env.local", ".env.example"}


def _is_scannable(path: Path, max_mb: int) -> bool:
    """Return True if the file should be scanned."""
    if not path.is_file():
        return False
    if path.suffix.lower() not in _SCANNABLE_EXTS and path.name.lower() not in _SCANNABLE_NAMES:
        return False
    try:
        return path.stat().st_size / (1024 * 1024) <= max_mb
    except OSError:
        return False


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Scan files under *target* for hardcoded secrets.

    Uses the same regex patterns as ``redaction.py``.  Reports the file
    and pattern type but **never** the actual secret value.

    Args:
        policy: Active security policy.
        target: File or directory to scan.

    Returns:
        Report string and list of scanned file paths.
    """
    max_mb = policy.limits.max_file_mb
    max_files = policy.limits.max_files
    patterns = get_patterns()

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

    findings: list[str] = []
    touched: list[str] = []

    for fpath in files_to_scan:
        touched.append(str(fpath))
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for name, regex in patterns:
            if regex.search(content):
                rel = fpath.relative_to(target) if target.is_dir() else fpath.name
                findings.append(f"  {rel}: {name}")

    if findings:
        header = f"Found {len(findings)} potential secret(s) in {len(files_to_scan)} file(s):\n"
        return header + "\n".join(findings), touched

    return f"No secrets detected in {len(files_to_scan)} file(s).", touched
