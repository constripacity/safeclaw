"""Tests for safeclaw.plugins.complexity_scan."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.plugins.complexity_scan import _analyze_file, _count_nesting, run
from safeclaw.policy import Policy


@pytest.fixture()
def policy(tmp_path: Path) -> Policy:
    return Policy(project_root=str(tmp_path), allowed_plugins=["complexity_scan"])


class TestCountNesting:
    def test_simple_function(self, tmp_path: Path) -> None:
        src = tmp_path / "simple.py"
        src.write_text("def f():\n    x = 1\n", encoding="utf-8")
        import ast

        tree = ast.parse(src.read_text(encoding="utf-8"))
        assert _count_nesting(tree) == 0

    def test_nested_if(self, tmp_path: Path) -> None:
        src = tmp_path / "nested.py"
        src.write_text(
            "def f():\n"
            "    if True:\n"
            "        if True:\n"
            "            if True:\n"
            "                pass\n",
            encoding="utf-8",
        )
        import ast

        tree = ast.parse(src.read_text(encoding="utf-8"))
        func = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]
        assert _count_nesting(func) >= 3


class TestAnalyzeFile:
    def test_clean_file(self, tmp_path: Path) -> None:
        src = tmp_path / "clean.py"
        src.write_text("def hello():\n    return 1\n", encoding="utf-8")
        assert _analyze_file(src) == []

    def test_too_many_params(self, tmp_path: Path) -> None:
        src = tmp_path / "params.py"
        src.write_text(
            "def f(a, b, c, d, e, f_arg, g):\n    pass\n",
            encoding="utf-8",
        )
        findings = _analyze_file(src)
        assert len(findings) == 1
        assert "params" in findings[0]

    def test_long_function(self, tmp_path: Path) -> None:
        lines = ["def long_func():"]
        for i in range(55):
            lines.append(f"    x{i} = {i}")
        src = tmp_path / "long.py"
        src.write_text("\n".join(lines) + "\n", encoding="utf-8")
        findings = _analyze_file(src)
        assert len(findings) == 1
        assert "lines" in findings[0]

    def test_deep_nesting(self, tmp_path: Path) -> None:
        src = tmp_path / "deep.py"
        src.write_text(
            "def f():\n"
            "    if True:\n"
            "        for x in []:\n"
            "            while True:\n"
            "                with open('f'):\n"
            "                    try:\n"
            "                        pass\n"
            "                    except:\n"
            "                        pass\n",
            encoding="utf-8",
        )
        findings = _analyze_file(src)
        assert len(findings) == 1
        assert "nesting" in findings[0]

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        src = tmp_path / "bad.py"
        src.write_text("def (broken:\n", encoding="utf-8")
        assert _analyze_file(src) == []

    def test_async_function(self, tmp_path: Path) -> None:
        src = tmp_path / "async_func.py"
        src.write_text(
            "async def f(a, b, c, d, e, f_arg, g):\n    pass\n",
            encoding="utf-8",
        )
        findings = _analyze_file(src)
        assert len(findings) == 1
        assert "params" in findings[0]


class TestComplexityScanRun:
    def test_clean_project(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("def f():\n    pass\n", encoding="utf-8")
        report, touched = run(policy, tmp_path)
        assert "No complexity issues" in report
        assert len(touched) >= 1

    def test_complex_project(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text(
            "def f(a, b, c, d, e, f_arg, g):\n    pass\n",
            encoding="utf-8",
        )
        report, touched = run(policy, tmp_path)
        assert "complexity issues" in report.lower()
        assert "params" in report

    def test_single_file_target(self, policy: Policy, tmp_path: Path) -> None:
        src = tmp_path / "one.py"
        src.write_text("def f():\n    pass\n", encoding="utf-8")
        report, touched = run(policy, src)
        assert "1 Python file" in report

    def test_non_python_file_ignored(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "data.txt").write_text("not python", encoding="utf-8")
        report, touched = run(policy, tmp_path)
        assert "0 Python file" in report
