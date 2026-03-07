"""Tests for safeclaw.export."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from safeclaw.audit import AuditEvent, write_audit
from safeclaw.cli import app
from safeclaw.export import export_audit
from safeclaw.policy import Policy

runner = CliRunner()


@pytest.fixture()
def populated_project(tmp_path: Path) -> tuple[Path, Policy]:
    """Create a project with audit entries."""
    pol = Policy(project_root=str(tmp_path), allowed_plugins=["todo_scan"])
    for i in range(5):
        write_audit(
            tmp_path,
            AuditEvent(
                action=f"action_{i}",
                status="ok" if i % 2 == 0 else "error",
                detail=f"detail {i}",
                touched_files=[f"file{i}.py"],
            ),
        )
    return tmp_path, pol


class TestExportCsv:
    def test_csv_has_header(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="csv", count=10)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert "timestamp" in header
        assert "action" in header

    def test_csv_row_count(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="csv", count=10)
        lines = result.strip().split("\n")
        assert len(lines) == 6  # 1 header + 5 data rows

    def test_csv_touched_files_semicolon_separated(
        self, populated_project: tuple[Path, Policy]
    ) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="csv", count=1)
        assert "file4.py" in result


class TestExportJson:
    def test_json_valid(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="json", count=10)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 5

    def test_json_entry_structure(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="json", count=1)
        data = json.loads(result)
        assert "action" in data[0]
        assert "timestamp" in data[0]


class TestExportHtml:
    def test_html_contains_table(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="html", count=10)
        assert "<table>" in result
        assert "</table>" in result
        assert "SafeClaw Audit Export" in result

    def test_html_contains_entries(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        result = export_audit(pol, fmt="html", count=10)
        assert "action_0" in result

    def test_html_escapes_special_chars(self, tmp_path: Path) -> None:
        """HTML export should escape < > & characters."""
        pol = Policy(project_root=str(tmp_path))
        write_audit(
            tmp_path,
            AuditEvent(action="test", status="ok", detail="<script>alert('xss')</script>"),
        )
        result = export_audit(pol, fmt="html", count=1)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestExportToFile:
    def test_writes_to_file(self, populated_project: tuple[Path, Policy]) -> None:
        root, pol = populated_project
        out = root / "export.json"
        export_audit(pol, fmt="json", count=5, output_path=out)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data) == 5


class TestExportInvalidFormat:
    def test_unknown_format_raises(self, populated_project: tuple[Path, Policy]) -> None:
        _, pol = populated_project
        with pytest.raises(ValueError, match="Unknown export format"):
            export_audit(pol, fmt="xml")


class TestExportEmpty:
    def test_empty_audit_csv(self, tmp_path: Path) -> None:
        pol = Policy(project_root=str(tmp_path))
        result = export_audit(pol, fmt="csv", count=10)
        lines = result.strip().split("\n")
        assert len(lines) == 1  # header only

    def test_empty_audit_json(self, tmp_path: Path) -> None:
        pol = Policy(project_root=str(tmp_path))
        result = export_audit(pol, fmt="json", count=10)
        assert json.loads(result) == []

    def test_empty_audit_html(self, tmp_path: Path) -> None:
        pol = Policy(project_root=str(tmp_path))
        result = export_audit(pol, fmt="html", count=10)
        assert "<table>" in result


class TestExportCli:
    def test_export_stdout_json(self, tmp_path: Path) -> None:
        pol_path = tmp_path / "policy.yaml"
        pol_path.write_text(f'project_root: "{tmp_path.as_posix()}"\n', encoding="utf-8")
        write_audit(tmp_path, AuditEvent(action="test", status="ok"))
        result = runner.invoke(app, ["export", "--format", "json", "--policy", str(pol_path)])
        assert result.exit_code == 0

    def test_export_to_file(self, tmp_path: Path) -> None:
        pol_path = tmp_path / "policy.yaml"
        pol_path.write_text(f'project_root: "{tmp_path.as_posix()}"\n', encoding="utf-8")
        write_audit(tmp_path, AuditEvent(action="test", status="ok"))
        out = tmp_path / "out.csv"
        result = runner.invoke(
            app, ["export", str(out), "--format", "csv", "--policy", str(pol_path)]
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_export_invalid_format(self, tmp_path: Path) -> None:
        pol_path = tmp_path / "policy.yaml"
        pol_path.write_text(f'project_root: "{tmp_path.as_posix()}"\n', encoding="utf-8")
        result = runner.invoke(app, ["export", "--format", "xml", "--policy", str(pol_path)])
        assert result.exit_code == 1

    def test_export_html_format(self, tmp_path: Path) -> None:
        pol_path = tmp_path / "policy.yaml"
        pol_path.write_text(f'project_root: "{tmp_path.as_posix()}"\n', encoding="utf-8")
        write_audit(tmp_path, AuditEvent(action="test", status="ok"))
        result = runner.invoke(app, ["export", "--format", "html", "--policy", str(pol_path)])
        assert result.exit_code == 0
        assert "Audit" in result.output and "Export" in result.output
