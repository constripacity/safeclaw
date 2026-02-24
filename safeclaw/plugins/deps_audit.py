"""Plugin: dependency health check (static analysis, no network)."""

from __future__ import annotations

import re
from pathlib import Path

from safeclaw.policy import Policy


def _parse_requirements_txt(path: Path) -> list[tuple[str, str]]:
    """Parse a requirements.txt file into (name, specifier) pairs."""
    deps: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*(.*)", line)
        if match:
            deps.append((match.group(1), match.group(2).strip()))
    return deps


def _parse_pyproject_toml(path: Path) -> list[tuple[str, str]]:
    """Extract dependency names/specifiers from pyproject.toml."""
    deps: list[tuple[str, str]] = []
    in_deps = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if stripped == "]":
                break
            # Lines look like: "typer>=0.12.0",
            match = re.match(r'"([A-Za-z0-9_\-\.]+)\s*(.*?)"', stripped)
            if match:
                deps.append((match.group(1), match.group(2).strip().rstrip(",")))
    return deps


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Audit declared dependencies for the project at *target*.

    Reads ``requirements.txt`` or ``pyproject.toml`` and lists declared
    dependencies.  Flags any pinned to very old-looking versions as a
    basic heuristic.  No network calls are made.

    Args:
        policy: Active security policy.
        target: Project directory to inspect.

    Returns:
        Summary string and list of dependency files found.
    """
    if target.is_file():
        target = target.parent

    deps: list[tuple[str, str]] = []
    touched: list[str] = []

    req_txt = target / "requirements.txt"
    pyproject = target / "pyproject.toml"

    if req_txt.is_file():
        deps.extend(_parse_requirements_txt(req_txt))
        touched.append(str(req_txt))

    if pyproject.is_file():
        deps.extend(_parse_pyproject_toml(pyproject))
        touched.append(str(pyproject))

    if not deps:
        return "No dependency files found (requirements.txt / pyproject.toml).", touched

    parts: list[str] = [f"Found {len(deps)} declared dependency/ies:"]
    warnings: list[str] = []

    for name, spec in deps:
        parts.append(f"  {name} {spec}")
        # Basic heuristic: flag exact pins to 0.x or very old-looking versions
        pin_match = re.match(r"==\s*(\d+)", spec)
        if pin_match and int(pin_match.group(1)) == 0:
            warnings.append(f"  {name} {spec} — pinned to 0.x (may be outdated)")

    if warnings:
        parts.append(f"\nWarnings ({len(warnings)}):")
        parts.extend(warnings)

    return "\n".join(parts), touched
