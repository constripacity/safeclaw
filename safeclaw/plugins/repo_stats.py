"""Plugin: repository statistics — file counts, lines of code, file types."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from safeclaw.policy import Policy

# Extensions treated as text/code for line counting.
_CODE_EXTENSIONS: set[str] = {
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
    ".sql",
    ".r",
    ".kt",
    ".swift",
    ".cs",
}


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Gather repository statistics for the directory at *target*.

    Args:
        policy: Active security policy.
        target: Directory to analyse.

    Returns:
        Formatted statistics string and list of counted file paths.
    """
    if target.is_file():
        target = target.parent

    max_mb = policy.limits.max_file_mb
    max_files = policy.limits.max_files

    ext_counts: Counter[str] = Counter()
    total_lines = 0
    total_files = 0
    touched: list[str] = []

    for p in sorted(target.rglob("*")):
        if total_files >= max_files:
            break
        if not p.is_file():
            continue

        total_files += 1
        ext = p.suffix.lower() if p.suffix else "(no ext)"
        ext_counts[ext] += 1
        touched.append(str(p))

        if ext in _CODE_EXTENSIONS:
            try:
                size_mb = p.stat().st_size / (1024 * 1024)
                if size_mb > max_mb:
                    continue
                total_lines += len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue

    parts: list[str] = [
        f"Repository: {target.name}",
        f"Total files: {total_files}",
        f"Total lines of code: {total_lines}",
        "",
        "File type distribution:",
    ]

    for ext, count in ext_counts.most_common(15):
        parts.append(f"  {ext:12s} {count}")

    return "\n".join(parts), touched
