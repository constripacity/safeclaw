"""SafeClaw Web Dashboard — localhost-only FastAPI app."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from safeclaw.audit import AuditEvent, read_audit, write_audit
from safeclaw.policy import Policy
from safeclaw.runner import get_registry, run_plugin

# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

TOKEN_DIR = ".safeclaw"
TOKEN_FILE = "dashboard_token"


def get_or_create_token(project_root: Path) -> str:
    """Read or generate the dashboard bearer token.

    Stored in ``.safeclaw/dashboard_token`` inside the project root.
    """
    root = Path(project_root).resolve()
    token_dir = root / TOKEN_DIR
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / TOKEN_FILE

    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()

    token = secrets.token_urlsafe(32)
    token_path.write_text(token, encoding="utf-8")
    return token


# ---------------------------------------------------------------------------
# HTML templates (inline)
# ---------------------------------------------------------------------------

_CSS = """\
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e;
       color: #e0e0e0; margin: 0; padding: 0; }
nav { background: #16213e; padding: 12px 24px; display: flex; gap: 24px;
      align-items: center; border-bottom: 1px solid #0f3460; }
nav a { color: #94b8ff; text-decoration: none; font-weight: 500; }
nav a:hover { color: #fff; }
nav .brand { color: #e94560; font-weight: 700; font-size: 1.1em; }
.container { max-width: 960px; margin: 24px auto; padding: 0 24px; }
h1 { color: #e94560; margin-bottom: 8px; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th { background: #16213e; text-align: left; padding: 10px 12px; }
td { padding: 8px 12px; border-bottom: 1px solid #16213e; }
.ok { color: #4ecca3; } .denied, .error { color: #e94560; }
.disabled { color: #666; } .enabled { color: #4ecca3; }
pre { background: #16213e; padding: 16px; border-radius: 8px;
      overflow-x: auto; font-size: 0.9em; }
.pill { display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.85em; }
.pill-ok { background: #1b4332; color: #4ecca3; }
.pill-no { background: #3d0000; color: #e94560; }
"""

_NAV = """\
<nav>
  <span class="brand">SafeClaw</span>
  <a href="/">Dashboard</a>
  <a href="/audit">Audit Log</a>
  <a href="/policy">Policy</a>
  <a href="/plugins">Plugins</a>
</nav>
"""


def _page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html><head><title>{title}</title>"
        f"<style>{_CSS}</style></head><body>{_NAV}"
        f'<div class="container"><h1>{title}</h1>{body}</div></body></html>'
    )


def _bool_pill(val: bool, yes: str = "yes", no: str = "no") -> str:
    cls = "pill-ok" if val else "pill-no"
    text = yes if val else no
    return f'<span class="pill {cls}">{text}</span>'


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Request body for POST /run."""

    plugin: str
    target: str = "./"


class PlanRequest(BaseModel):
    """Request body for POST /plan."""

    task: str


def create_app(policy: Policy) -> FastAPI:
    """Create and return the FastAPI dashboard application."""
    app = FastAPI(title="SafeClaw Dashboard", docs_url=None, redoc_url=None)
    token = get_or_create_token(policy.root_path())

    # --- Auth dependency ---
    def require_auth(request: Request) -> None:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    # --- Routes ---

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, _auth: None = Depends(require_auth)) -> str:
        write_audit(
            policy.root_path(),
            AuditEvent(action="dashboard", status="ok", detail="GET /"),
        )
        entries = read_audit(policy.root_path(), last_n=10)
        rows = ""
        for e in entries:
            ts = e.get("timestamp", "?")[:19]
            cls = "ok" if e.get("status") == "ok" else "error"
            rows += (
                f"<tr><td>{ts}</td><td>{e.get('action', '?')}</td>"
                f'<td class="{cls}">{e.get("status", "?")}</td>'
                f"<td>{e.get('detail', '')[:80]}</td></tr>"
            )

        net = _bool_pill(policy.allow_network, "allowed", "denied")
        sh = _bool_pill(policy.allow_shell, "allowed", "denied")
        plan = _bool_pill(policy.planner.enabled)

        body = (
            f"<h2>Policy Summary</h2>"
            f"<p>Network: {net} | Shell: {sh} | Planner: {plan}</p>"
            f"<h2>Recent Audit Log</h2>"
            f"<table><tr><th>Time</th><th>Action</th><th>Status</th>"
            f"<th>Detail</th></tr>{rows}</table>"
        )
        return _page("Dashboard", body)

    @app.get("/audit", response_class=HTMLResponse)
    def audit_page(
        request: Request,
        page: int = 1,
        _auth: None = Depends(require_auth),
    ) -> str:
        write_audit(
            policy.root_path(),
            AuditEvent(action="dashboard", status="ok", detail="GET /audit"),
        )
        per_page = 20
        entries = read_audit(policy.root_path(), last_n=page * per_page)
        start = (page - 1) * per_page
        page_entries = entries[start : start + per_page]

        rows = ""
        for e in page_entries:
            ts = e.get("timestamp", "?")[:19]
            cls = "ok" if e.get("status") == "ok" else "error"
            rows += (
                f"<tr><td>{ts}</td><td>{e.get('action', '?')}</td>"
                f'<td class="{cls}">{e.get("status", "?")}</td>'
                f"<td>{e.get('detail', '')[:100]}</td></tr>"
            )

        nav_links = ""
        if page > 1:
            nav_links += f'<a href="/audit?page={page - 1}">&laquo; Previous</a> '
        if len(entries) >= page * per_page:
            nav_links += f'<a href="/audit?page={page + 1}">Next &raquo;</a>'

        body = (
            f"<table><tr><th>Time</th><th>Action</th><th>Status</th>"
            f"<th>Detail</th></tr>{rows}</table>"
            f"<p>{nav_links}</p>"
        )
        return _page("Audit Log", body)

    @app.get("/policy", response_class=HTMLResponse)
    def policy_page(request: Request, _auth: None = Depends(require_auth)) -> str:
        write_audit(
            policy.root_path(),
            AuditEvent(action="dashboard", status="ok", detail="GET /policy"),
        )
        policy_dict = policy.model_dump()
        formatted = yaml.dump(policy_dict, default_flow_style=False, sort_keys=False)
        body = f"<pre>{formatted}</pre>"
        return _page("Policy", body)

    @app.get("/plugins", response_class=HTMLResponse)
    def plugins_page(request: Request, _auth: None = Depends(require_auth)) -> str:
        write_audit(
            policy.root_path(),
            AuditEvent(action="dashboard", status="ok", detail="GET /plugins"),
        )
        registry = get_registry()
        rows = ""
        for name in sorted(registry):
            allowed = name in policy.allowed_plugins
            cls = "enabled" if allowed else "disabled"
            badge = _bool_pill(allowed)
            doc = (registry[name].__doc__ or "").split("\n")[0]
            rows += f'<tr><td>{name}</td><td class="{cls}">{badge}</td><td>{doc}</td></tr>'

        body = f"<table><tr><th>Plugin</th><th>Allowed</th><th>Description</th></tr>{rows}</table>"
        return _page("Plugins", body)

    @app.post("/run")
    def run_endpoint(
        body: RunRequest,
        request: Request,
        _auth: None = Depends(require_auth),
    ) -> dict[str, Any]:
        write_audit(
            policy.root_path(),
            AuditEvent(
                action="dashboard",
                status="ok",
                detail=f"POST /run plugin={body.plugin}",
            ),
        )
        if body.plugin not in policy.allowed_plugins:
            raise HTTPException(
                status_code=403,
                detail=f"Plugin '{body.plugin}' is not allowed by policy",
            )
        result = run_plugin(policy, body.plugin, body.target)
        return {"ok": result.ok, "message": result.message, "touched_files": result.touched_files}

    @app.post("/plan")
    def plan_endpoint(
        body: PlanRequest,
        request: Request,
        _auth: None = Depends(require_auth),
    ) -> dict[str, Any]:
        from safeclaw.planner import (
            Planner,
            PlannerError,
            validate_plan,
        )

        write_audit(
            policy.root_path(),
            AuditEvent(action="dashboard", status="ok", detail=f"POST /plan task={body.task}"),
        )

        try:
            planner = Planner(policy)
            plan = planner.plan(body.task)
            result = validate_plan(plan, policy)
            return {
                "steps": [s.model_dump() for s in plan.steps],
                "validated": result.validated,
                "rejected_steps": result.rejected_steps,
            }
        except PlannerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
