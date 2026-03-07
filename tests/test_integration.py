"""End-to-end integration tests for SafeClaw v0.4.0."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from safeclaw.audit import AUDIT_DIR, AUDIT_FILE, rotate_audit
from safeclaw.cli import app
from safeclaw.policy import Policy

runner = CliRunner()


@pytest.fixture()
def full_project(tmp_path: Path) -> Path:
    """Create a full project with all test artifacts."""
    # Python file with TODO + secret + complexity issues
    (tmp_path / "app.py").write_text(
        "# TODO: fix this\n"
        "# FIXME: broken\n"
        'API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"\n'
        "def complex_func(a, b, c, d, e, f_arg, g):\n"
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

    # .env with secret
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-placeholder1234567890abcdefghijklmnop\n",
        encoding="utf-8",
    )

    # Build log
    (tmp_path / "build.log").write_text(
        "[INFO] Starting build\n[ERROR] Failed to compile\n[INFO] Done\n",
        encoding="utf-8",
    )

    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\ndependencies = [\n    "requests>=2.0",\n]\n',
        encoding="utf-8",
    )

    # LICENSE file
    (tmp_path / "LICENSE").write_text(
        "MIT License\n\nPermission is hereby granted, free of charge",
        encoding="utf-8",
    )

    # Fake .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    heads = git_dir / "refs" / "heads"
    heads.mkdir(parents=True)
    (heads / "main").write_text("abc123\n", encoding="utf-8")
    tags = git_dir / "refs" / "tags"
    tags.mkdir(parents=True)
    logs = git_dir / "logs"
    logs.mkdir()
    (logs / "HEAD").write_text(
        "0000000 abc1234 Dev <dev@test.com> 1700000000 +0000\tcommit: init\n",
        encoding="utf-8",
    )

    # Policy with all 8 plugins + dashboard enabled
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "project_root: " + str(tmp_path).replace("\\", "/") + "\n"
        "allowed_plugins:\n"
        "  - todo_scan\n"
        "  - secrets_scan\n"
        "  - log_summarize\n"
        "  - deps_audit\n"
        "  - repo_stats\n"
        "  - license_check\n"
        "  - complexity_scan\n"
        "  - git_history\n"
        "dashboard:\n"
        "  enabled: true\n"
        "  host: 127.0.0.1\n"
        "  port: 8321\n",
        encoding="utf-8",
    )
    return tmp_path


class TestPluginsThroughCLI:
    """All 8 plugins work through the CLI."""

    @pytest.mark.parametrize(
        "cmd,plugin_marker",
        [
            (["todo"], "TODO"),
            (["secrets"], "secret"),
            (["deps"], "requests"),
            (["stats"], "Total files"),
            (["license"], "MIT"),
            (["complexity"], "complexity"),
            (["git-history"], "refs/heads/main"),
        ],
    )
    def test_plugin_via_cli(self, full_project: Path, cmd: list[str], plugin_marker: str) -> None:
        policy_path = str(full_project / "policy.yaml")
        result = runner.invoke(app, [*cmd, str(full_project), "--policy", policy_path])
        assert result.exit_code == 0
        assert plugin_marker.lower() in result.output.lower()

    def test_summarize_via_cli(self, full_project: Path) -> None:
        policy_path = str(full_project / "policy.yaml")
        log_path = str(full_project / "build.log")
        result = runner.invoke(app, ["summarize", log_path, "--policy", policy_path])
        assert result.exit_code == 0
        assert "ERROR" in result.output


class TestNewPluginsViaAPI:
    """New plugins work through the dashboard API."""

    def test_license_scan_api(self, full_project: Path) -> None:
        from safeclaw.dashboard import create_app, get_or_create_token

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["license_check"],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/scan",
            json={"plugin": "license_check", "target": str(full_project)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "MIT" in data["message"]

    def test_complexity_scan_api(self, full_project: Path) -> None:
        from safeclaw.dashboard import create_app, get_or_create_token

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["complexity_scan"],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/scan",
            json={"plugin": "complexity_scan", "target": str(full_project)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_git_history_scan_api(self, full_project: Path) -> None:
        from safeclaw.dashboard import create_app, get_or_create_token

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["git_history"],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/scan",
            json={"plugin": "git_history", "target": str(full_project)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "main" in data["message"]


class TestRateLimiting:
    """Rate limiter returns 429 when exceeded."""

    def test_get_rate_limit(self, full_project: Path) -> None:
        from safeclaw.dashboard import _rate_limiter, create_app, get_or_create_token

        # Reset rate limiter state
        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["todo_scan"],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        # Exhaust the GET limit
        for _ in range(60):
            resp = client.get("/api/status", headers=headers)
            assert resp.status_code == 200

        # Next request should be rate limited
        resp = client.get("/api/status", headers=headers)
        assert resp.status_code == 429

    def test_post_rate_limit(self, full_project: Path) -> None:
        from safeclaw.dashboard import _rate_limiter, create_app, get_or_create_token

        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["todo_scan"],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        for _ in range(30):
            resp = client.post(
                "/api/scan",
                json={"plugin": "todo_scan", "target": str(full_project)},
                headers=headers,
            )
            assert resp.status_code == 200

        resp = client.post(
            "/api/scan",
            json={"plugin": "todo_scan", "target": str(full_project)},
            headers=headers,
        )
        assert resp.status_code == 429


class TestSecurityHeaders:
    """Security headers are present on all responses."""

    def test_headers_on_api(self, full_project: Path) -> None:
        from safeclaw.dashboard import _rate_limiter, create_app, get_or_create_token

        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["todo_scan"],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/api/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "default-src" in resp.headers["Content-Security-Policy"]
        assert resp.headers["Cache-Control"] == "no-store"

    def test_headers_on_health(self, full_project: Path) -> None:
        from safeclaw.dashboard import _rate_limiter, create_app

        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=[],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)

        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["Cache-Control"] == "no-store"


class TestHealthEndpoint:
    """GET /health requires no auth."""

    def test_health_no_auth(self, full_project: Path) -> None:
        from safeclaw.dashboard import _rate_limiter, create_app

        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=[],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)

        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_not_rate_limited(self, full_project: Path) -> None:
        from safeclaw.dashboard import _rate_limiter, create_app

        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=[],
        )
        policy.dashboard.enabled = True
        app = create_app(policy)

        from starlette.testclient import TestClient

        client = TestClient(app)
        # Health should always respond even beyond rate limit
        for _ in range(65):
            resp = client.get("/health")
            assert resp.status_code == 200


class TestAuditRotation:
    """Audit log rotation works correctly."""

    def test_rotate_creates_backup(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / AUDIT_DIR
        audit_dir.mkdir()
        audit_file = audit_dir / AUDIT_FILE
        audit_file.write_text('{"test": true}\n', encoding="utf-8")

        result = rotate_audit(tmp_path)
        assert result is not None
        assert result.name == f"{AUDIT_FILE}.1"
        assert result.exists()
        assert not audit_file.exists()

    def test_rotate_shifts_existing(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / AUDIT_DIR
        audit_dir.mkdir()
        audit_file = audit_dir / AUDIT_FILE
        audit_file.write_text('{"current": true}\n', encoding="utf-8")
        (audit_dir / f"{AUDIT_FILE}.1").write_text('{"old": true}\n', encoding="utf-8")

        rotate_audit(tmp_path)
        assert (audit_dir / f"{AUDIT_FILE}.1").exists()
        assert (audit_dir / f"{AUDIT_FILE}.2").exists()
        assert not audit_file.exists()

    def test_rotate_empty_returns_none(self, tmp_path: Path) -> None:
        assert rotate_audit(tmp_path) is None


class TestAuditToAPIRoundTrip:
    """CLI scan creates audit entry visible via API."""

    def test_cli_scan_then_api_audit(self, full_project: Path) -> None:
        policy_path = str(full_project / "policy.yaml")
        runner.invoke(app, ["todo", str(full_project), "--policy", policy_path])

        from safeclaw.dashboard import _rate_limiter, create_app, get_or_create_token

        _rate_limiter._windows.clear()

        policy = Policy(
            project_root=str(full_project),
            allowed_plugins=["todo_scan"],
        )
        policy.dashboard.enabled = True
        dash_app = create_app(policy)
        token = get_or_create_token(full_project)

        from starlette.testclient import TestClient

        client = TestClient(dash_app)
        resp = client.get(
            "/api/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        actions = [e["action"] for e in entries]
        assert "todo_scan" in actions


class TestAuditRotateCLI:
    """safeclaw audit --rotate works."""

    def test_rotate_via_cli(self, full_project: Path) -> None:
        policy_path = str(full_project / "policy.yaml")
        # Create some audit entries first
        runner.invoke(app, ["todo", str(full_project), "--policy", policy_path])
        result = runner.invoke(app, ["audit", "--rotate", "--policy", policy_path])
        assert result.exit_code == 0
        assert "rotated" in result.output.lower()

    def test_rotate_empty_via_cli(self, full_project: Path) -> None:
        policy_path = str(full_project / "policy.yaml")
        result = runner.invoke(app, ["audit", "--rotate", "--policy", policy_path])
        assert result.exit_code == 0
        assert "nothing" in result.output.lower() or "empty" in result.output.lower()
