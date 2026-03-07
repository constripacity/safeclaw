"""Plugin: analyze git history without shell access.

Reads .git directory structure directly. Does not use subprocess or shell.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from safeclaw.policy import Policy


def _read_head_ref(git_dir: Path) -> str | None:
    """Read the current branch from .git/HEAD."""
    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    content = head.read_text(encoding="utf-8", errors="replace").strip()
    if content.startswith("ref: "):
        return content[5:]
    return content[:12] + "..."


def _count_refs(git_dir: Path) -> dict[str, int]:
    """Count local branches and tags from refs directory."""
    counts: dict[str, int] = {"branches": 0, "tags": 0}
    heads_dir = git_dir / "refs" / "heads"
    tags_dir = git_dir / "refs" / "tags"

    if heads_dir.is_dir():
        counts["branches"] = sum(
            1 for p in heads_dir.rglob("*") if p.is_file()
        )
    if tags_dir.is_dir():
        counts["tags"] = sum(
            1 for p in tags_dir.rglob("*") if p.is_file()
        )

    return counts


def _parse_reflog(
    git_dir: Path, max_entries: int = 200
) -> list[dict[str, str]]:
    """Parse .git/logs/HEAD for recent commit activity."""
    reflog = git_dir / "logs" / "HEAD"
    if not reflog.is_file():
        return []

    entries: list[dict[str, str]] = []
    pattern = re.compile(
        r"^[0-9a-f]+ [0-9a-f]+ (.+?) <(.+?)> (\d+) [+\-]\d{4}\t(.*)$"
    )

    try:
        lines = reflog.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return []

    for line in reversed(lines[-max_entries:]):
        match = pattern.match(line)
        if match:
            entries.append(
                {
                    "author": match.group(1),
                    "email": match.group(2),
                    "timestamp": match.group(3),
                    "action": match.group(4),
                }
            )

    return entries


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Analyze git history for the repository at *target*.

    Reads the .git directory directly — no shell access required.

    Args:
        policy: Active security policy.
        target: File or directory within the repository.

    Returns:
        Report string and list of git files read.
    """
    if target.is_file():
        target = target.parent

    git_dir = target / ".git"
    if not git_dir.is_dir():
        return "No .git directory found. Is this a git repository?", []

    touched: list[str] = []
    parts: list[str] = [f"Git History: {target.name}"]

    head_ref = _read_head_ref(git_dir)
    if head_ref:
        touched.append(str(git_dir / "HEAD"))
        parts.append(f"Current HEAD: {head_ref}")

    refs = _count_refs(git_dir)
    parts.append(f"Local branches: {refs['branches']}")
    parts.append(f"Tags: {refs['tags']}")

    entries = _parse_reflog(git_dir)
    if entries:
        touched.append(str(git_dir / "logs" / "HEAD"))
        parts.append(f"Reflog entries: {len(entries)}")

        commit_entries = [
            e for e in entries if e["action"].startswith("commit")
        ]
        author_counts: Counter[str] = Counter()
        for e in commit_entries:
            author_counts[e["author"]] += 1

        parts.append(f"Commits in reflog: {len(commit_entries)}")

        if author_counts:
            parts.append("\nTop contributors:")
            for author, count in author_counts.most_common(5):
                parts.append(f"  {author}: {count} commit(s)")
    else:
        parts.append("Reflog: not available")

    return "\n".join(parts), touched
