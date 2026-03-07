"""Tests for safeclaw.dashboard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


class TestApiEndpoints:
    def test_api_status(self, client: TestClient) -> None:
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "project_root" in data
        assert "plugins_active" in data
        assert "total_scans" in data
        assert isinstance(data["network"], bool)
        assert isinstance(data["shell"], bool)

    def test_api_audit(self, client: TestClient) -> None:
        resp = client.get("/api/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data

    def test_api_audit_pagination(self, client: TestClient) -> None:
        resp = client.get("/api/audit?page=1&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["page"] == 1

    def test_api_audit_filter_by_status(self, client: TestClient) -> None:
        resp = client.get("/api/audit?status=ok")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["entries"], list)

    def test_api_plugins(self, client: TestClient) -> None:
        resp = client.get("/api/plugins")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = [p["name"] for p in data]
        assert "todo_scan" in names
        for p in data:
            assert "name" in p
            assert "allowed" in p
            assert "description" in p

    def test_api_policy(self, client: TestClient) -> None:
        resp = client.get("/api/policy")
        assert resp.status_code == 200
        data = resp.json()
        assert "project_root" in data
        assert "allowed_plugins" in data
        assert "limits" in data

    def test_api_scan_allowed_plugin(self, client: TestClient, dashboard_policy: Policy) -> None:
        root = dashboard_policy.root_path()
        (root / "test.py").write_text("# TODO: fix\n", encoding="utf-8")
        resp = client.post("/api/scan", json={"plugin": "todo_scan", "target": str(root)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_api_scan_denied_plugin(self, client: TestClient) -> None:
        resp = client.post("/api/scan", json={"plugin": "evil_plugin"})
        assert resp.status_code == 403


class TestApiAuth:
    def test_api_get_endpoints_require_auth(self, unauth_client: TestClient) -> None:
        for path in ["/api/status", "/api/audit", "/api/plugins", "/api/policy"]:
            resp = unauth_client.get(path)
            assert resp.status_code == 401, f"{path} should require auth"

    def test_api_post_endpoints_require_auth(self, unauth_client: TestClient) -> None:
        for path in ["/api/scan", "/api/plan", "/api/plan/execute"]:
            resp = unauth_client.post(path, json={"plugin": "x", "task": "x"})
            assert resp.status_code == 401, f"{path} should require auth"


class TestPlanEndpoints:
    def test_plan_endpoint_planner_disabled(self, client: TestClient) -> None:
        resp = client.post("/plan", json={"task": "scan for issues"})
        assert resp.status_code == 400

    def test_api_plan_planner_disabled(self, client: TestClient) -> None:
        resp = client.post("/api/plan", json={"task": "scan everything"})
        assert resp.status_code == 400

    def test_api_plan_execute_planner_disabled(self, client: TestClient) -> None:
        resp = client.post("/api/plan/execute", json={"task": "scan"})
        assert resp.status_code == 400


class TestGoldenDashboard:
    def test_golden_page_returns_404_without_template(self, tmp_path: Path) -> None:
        """Golden page returns 404 when template file does not exist."""
        pol = Policy(
            project_root=str(tmp_path),
            allowed_plugins=["todo_scan"],
            dashboard=DashboardConfig(enabled=True),
        )
        app = create_app(pol)
        token = get_or_create_token(pol.root_path())
        c = TestClient(app, headers={"Authorization": f"Bearer {token}"})
        orig_exists = Path.exists

        def fake_exists(self: Path) -> bool:
            if "golden.html" in str(self):
                return False
            return orig_exists(self)

        with patch.object(Path, "exists", fake_exists):
            resp = c.get("/golden")
        assert resp.status_code == 404

    def test_golden_redirect(self, tmp_path: Path) -> None:
        """When golden=True, / redirects to /golden."""
        pol = Policy(
            project_root=str(tmp_path),
            allowed_plugins=["todo_scan"],
            dashboard=DashboardConfig(enabled=True),
        )
        app = create_app(pol, golden=True)
        token = get_or_create_token(pol.root_path())
        c = TestClient(app, headers={"Authorization": f"Bearer {token}"}, follow_redirects=False)
        resp = c.get("/")
        assert resp.status_code == 302
        assert "/golden" in resp.headers["location"]
