"""Tests for the secrets_scan plugin."""

from pathlib import Path

from safeclaw.plugins.secrets_scan import run
from safeclaw.policy import Policy


class TestSecretsScan:
    def test_detects_openai_key(self, policy: Policy, tmp_project: Path) -> None:
        message, _ = run(policy, tmp_project)
        assert "OPENAI_KEY" in message

    def test_detects_aws_key(self, policy: Policy, tmp_project: Path) -> None:
        message, _ = run(policy, tmp_project)
        assert "AWS_KEY" in message

    def test_no_actual_secret_in_output(self, policy: Policy, tmp_project: Path) -> None:
        message, _ = run(policy, tmp_project)
        assert "sk-placeholder" not in message
        assert "AKIAIOSFODNN7EXAMPLE" not in message

    def test_clean_project_no_findings(self, tmp_path: Path) -> None:
        clean = tmp_path / "clean.py"
        clean.write_text("x = 42\n", encoding="utf-8")
        pol = Policy(project_root=str(tmp_path))
        message, _ = run(pol, tmp_path)
        assert "No secrets" in message

    def test_single_file_mode(self, policy: Policy, tmp_project: Path) -> None:
        """Scanning a single file should work."""
        target = tmp_project / ".env"
        msg, touched = run(policy, target)
        assert "OPENAI_KEY" in msg
        assert len(touched) == 1

    def test_max_files_limit(self, tmp_path: Path) -> None:
        """Only max_files files should be scanned."""
        from safeclaw.policy import Limits

        pol = Policy(
            project_root=str(tmp_path),
            limits=Limits(max_files=1),
        )
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"key = 'sk-{'a' * 30}'\n", encoding="utf-8")
        _, touched = run(pol, tmp_path)
        assert len(touched) == 1
