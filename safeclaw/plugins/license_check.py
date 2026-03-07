"""Plugin: check for license files and identify license type."""

from __future__ import annotations

import re
from pathlib import Path

from safeclaw.policy import Policy

_LICENSE_NAMES: set[str] = {
    "license",
    "licence",
    "license.md",
    "licence.md",
    "license.txt",
    "licence.txt",
    "license.rst",
    "licence.rst",
    "copying",
    "copying.md",
    "copying.txt",
}

_LICENSE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "MIT",
        re.compile(
            r"MIT License|Permission is hereby granted, free of charge",
            re.IGNORECASE,
        ),
    ),
    (
        "Apache-2.0",
        re.compile(
            r"Apache License.*Version 2\.0|apache\.org/licenses/LICENSE-2\.0",
            re.IGNORECASE,
        ),
    ),
    (
        "GPL-3.0",
        re.compile(
            r"GNU GENERAL PUBLIC LICENSE.*Version 3|GPLv3",
            re.IGNORECASE,
        ),
    ),
    (
        "GPL-2.0",
        re.compile(
            r"GNU GENERAL PUBLIC LICENSE.*Version 2|GPLv2",
            re.IGNORECASE,
        ),
    ),
    (
        "BSD-3-Clause",
        re.compile(
            r"BSD 3-Clause|Redistribution and use.*three conditions",
            re.IGNORECASE,
        ),
    ),
    (
        "BSD-2-Clause",
        re.compile(r"BSD 2-Clause|Simplified BSD", re.IGNORECASE),
    ),
    ("ISC", re.compile(r"ISC License", re.IGNORECASE)),
    (
        "MPL-2.0",
        re.compile(r"Mozilla Public License.*2\.0", re.IGNORECASE),
    ),
    (
        "Unlicense",
        re.compile(
            r"This is free and unencumbered software|UNLICENSE",
            re.IGNORECASE,
        ),
    ),
]


def _detect_license_type(content: str) -> str:
    """Detect the license type from file content."""
    for name, pattern in _LICENSE_PATTERNS:
        if pattern.search(content):
            return name
    return "Unknown"


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Check for license files in the project at *target*.

    Args:
        policy: Active security policy.
        target: File or directory to inspect.

    Returns:
        Report string and list of license files found.
    """
    if target.is_file():
        target = target.parent

    touched: list[str] = []
    found_licenses: list[tuple[Path, str]] = []

    for p in sorted(target.iterdir()):
        if not p.is_file():
            continue
        if p.name.lower() in _LICENSE_NAMES:
            touched.append(str(p))
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                license_type = _detect_license_type(content)
                found_licenses.append((p, license_type))
            except OSError:
                found_licenses.append((p, "Unreadable"))

    if not found_licenses:
        pyproject = target / "pyproject.toml"
        if pyproject.is_file():
            touched.append(str(pyproject))
            try:
                content = pyproject.read_text(
                    encoding="utf-8", errors="replace"
                )
                match = re.search(r'license\s*=\s*"([^"]+)"', content)
                if match:
                    return (
                        "No LICENSE file found, but license declared in"
                        f" pyproject.toml: {match.group(1)}\n"
                        "Consider adding a LICENSE file to the project root.",
                        touched,
                    )
            except OSError:
                pass
        return "No LICENSE file found in the project root.", touched

    parts: list[str] = [f"Found {len(found_licenses)} license file(s):"]
    for fpath, ltype in found_licenses:
        parts.append(f"  {fpath.name}: {ltype}")

    return "\n".join(parts), touched
