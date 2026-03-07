"""Plugin: scan Python files for code complexity indicators using AST."""

from __future__ import annotations

import ast
from pathlib import Path

from safeclaw.policy import Policy

_MAX_LINES = 50
_MAX_PARAMS = 5
_MAX_NESTING = 4


def _count_nesting(node: ast.AST, current: int = 0) -> int:
    """Count the maximum nesting depth of control flow statements."""
    max_depth = current
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            max_depth = max(max_depth, _count_nesting(child, current + 1))
        else:
            max_depth = max(max_depth, _count_nesting(child, current))
    return max_depth


def _analyze_file(fpath: Path) -> list[str]:
    """Analyze a single Python file and return findings."""
    try:
        source = fpath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(fpath))
    except (SyntaxError, OSError):
        return []

    findings: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        name = node.name
        lineno = node.lineno

        # Line count
        end_lineno = getattr(node, "end_lineno", None)
        func_lines = (end_lineno - lineno + 1) if end_lineno is not None else 0

        # Parameter count
        args = node.args
        param_count = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
        if args.vararg:
            param_count += 1
        if args.kwarg:
            param_count += 1

        # Nesting depth
        nesting = _count_nesting(node)

        # Check thresholds
        issues: list[str] = []
        if func_lines > _MAX_LINES:
            issues.append(f"{func_lines} lines (>{_MAX_LINES})")
        if param_count > _MAX_PARAMS:
            issues.append(f"{param_count} params (>{_MAX_PARAMS})")
        if nesting > _MAX_NESTING:
            issues.append(f"nesting {nesting} (>{_MAX_NESTING})")

        if issues:
            findings.append(f"  L{lineno} {name}(): {', '.join(issues)}")

    return findings


def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
    """Scan Python files under *target* for complexity issues.

    Flags functions exceeding thresholds for line count, parameter
    count, or nesting depth.

    Args:
        policy: Active security policy.
        target: File or directory to scan.

    Returns:
        Report string and list of scanned file paths.
    """
    max_mb = policy.limits.max_file_mb
    max_files = policy.limits.max_files

    files_to_scan: list[Path] = []
    if target.is_file():
        if target.suffix == ".py":
            files_to_scan.append(target)
    else:
        for p in sorted(target.rglob("*.py")):
            if len(files_to_scan) >= max_files:
                break
            try:
                if p.stat().st_size / (1024 * 1024) <= max_mb:
                    files_to_scan.append(p)
            except OSError:
                continue

    all_findings: list[str] = []
    touched: list[str] = []

    for fpath in files_to_scan:
        touched.append(str(fpath))
        file_findings = _analyze_file(fpath)
        if file_findings:
            rel = fpath.relative_to(target) if target.is_dir() else fpath.name
            all_findings.append(f"  {rel}:")
            all_findings.extend(f"    {f}" for f in file_findings)

    if all_findings:
        n = len(files_to_scan)
        header = f"Found complexity issues in {n} Python file(s):\n"
        return header + "\n".join(all_findings), touched

    n = len(files_to_scan)
    return f"No complexity issues found in {n} Python file(s).", touched
