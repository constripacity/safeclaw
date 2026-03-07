"""Tests for safeclaw.plugins.license_check."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.plugins.license_check import _detect_license_type, run
from safeclaw.policy import Policy


@pytest.fixture()
def policy(tmp_path: Path) -> Policy:
    return Policy(project_root=str(tmp_path), allowed_plugins=["license_check"])


class TestDetectLicenseType:
    def test_mit(self) -> None:
        assert _detect_license_type("MIT License\n\nPermission is hereby granted") == "MIT"

    def test_apache(self) -> None:
        assert _detect_license_type("Apache License Version 2.0") == "Apache-2.0"

    def test_gpl3(self) -> None:
        assert _detect_license_type("GNU GENERAL PUBLIC LICENSE Version 3") == "GPL-3.0"

    def test_bsd3(self) -> None:
        assert _detect_license_type("BSD 3-Clause License") == "BSD-3-Clause"

    def test_unknown(self) -> None:
        assert _detect_license_type("Some proprietary license text") == "Unknown"


class TestLicenseCheckRun:
    def test_mit_license_found(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "LICENSE").write_text(
            "MIT License\n\nPermission is hereby granted, free of charge",
            encoding="utf-8",
        )
        report, touched = run(policy, tmp_path)
        assert "MIT" in report
        assert "1 license file" in report
        assert len(touched) == 1

    def test_no_license_file(self, policy: Policy, tmp_path: Path) -> None:
        report, touched = run(policy, tmp_path)
        assert "No LICENSE file found" in report

    def test_fallback_to_pyproject(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nlicense = "MIT"\n',
            encoding="utf-8",
        )
        report, touched = run(policy, tmp_path)
        assert "pyproject.toml" in report
        assert "MIT" in report

    def test_multiple_license_files(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        (tmp_path / "COPYING").write_text("GNU GENERAL PUBLIC LICENSE Version 3", encoding="utf-8")
        report, touched = run(policy, tmp_path)
        assert "2 license file" in report

    def test_file_target_uses_parent(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        target_file = tmp_path / "some_file.py"
        target_file.write_text("pass", encoding="utf-8")
        report, _touched = run(policy, target_file)
        assert "MIT" in report

    def test_licence_spelling(self, policy: Policy, tmp_path: Path) -> None:
        (tmp_path / "LICENCE.md").write_text("ISC License", encoding="utf-8")
        report, touched = run(policy, tmp_path)
        assert "ISC" in report
        assert len(touched) == 1

    def test_no_license_no_pyproject(self, policy: Policy, tmp_path: Path) -> None:
        # Empty directory — no LICENSE and no pyproject.toml
        report, touched = run(policy, tmp_path)
        assert "No LICENSE file found" in report
