"""Tests for safeclaw.dashboard."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from safeclaw.dashboard import create_app, get_or_create_token
from safeclaw.policy import DashboardConfig, Policy


@pytest.fixture()
def dashboard_policy(tmp_path: Path) -> Policy:
    """Policy with dashboard enabled, rooted at tmp_path."""
    return Policy(
        project_root=str(tmp_path),
        allowed_plugins=["todo_scan", "secrets_scan"],
        dashboard=DashboardConfig(enabled=True, host="127.0.0.1", port=8321),
    )


@pytest.fixture()
def client(dashboard_policy: Policy) -> TestClient:
    """TestClient with valid auth headers."""
    app = create_app(dashboard_policy)
    token = get_or_create_token(dashboard_policy.root_path())
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def unauth_client(dashboard_policy: Policy) -> TestClient:
    """TestClient without auth headers."""
    app = create_app(dashboard_policy)
    return TestClient(app)


class TestDashboardAuth:
    def test_no_token_returns_401(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/")
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self, dashboard_policy: Policy) -> None:
        app = create_app(dashboard_policy)
        bad_client = TestClient(app, headers={"Authorization": "Bearer wrong-token"})
        resp = bad_client.get("/")
        assert resp.status_code == 401

    def test_valid_token_returns_200(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200


class TestDashboardEndpoints:
    def test_home(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_audit_page(self, client: TestClient) -> None:
        resp = client.get("/audit")
        assert resp.status_code == 200
        assert "Audit" in resp.text

    def test_policy_page(self, client: TestClient) -> None:
        resp = client.get("/policy")
        assert resp.status_code == 200
        assert "project_root" in resp.text

    def test_plugins_page(self, client: TestClient) -> None:
        resp = client.get("/plugins")
        assert resp.status_code == 200
        assert "todo_scan" in resp.text


class TestDashboardRunEndpoint:
    def test_run_denied_plugin_returns_403(self, client: TestClient) -> None:
        resp = client.post("/run", json={"plugin": "evil_plugin", "target": "./"})
        assert resp.status_code == 403

    def test_run_valid_plugin(self, client: TestClient, dashboard_policy: Policy) -> None:
        # Create a file so todo_scan has something to scan
        root = dashboard_policy.root_path()
        (root / "test.py").write_text("# TODO: fix this\n", encoding="utf-8")
        resp = client.post("/run", json={"plugin": "todo_scan", "target": str(root)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True


class TestDashboardConfig:
    def test_default_host_is_localhost(self) -> None:
        p = Policy()
        assert p.dashboard.host == "127.0.0.1"

    def test_token_persists(self, tmp_path: Path) -> None:
        token1 = get_or_create_token(tmp_path)
        token2 = get_or_create_token(tmp_path)
        assert token1 == token2
        assert len(token1) > 20
