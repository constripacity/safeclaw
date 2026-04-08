"""SafeClaw Web Dashboard — localhost-only FastAPI app."""

from __future__ import annotations

import html as _html
import secrets
import time
from collections import deque
from pathlib import Path
from typing import Any

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from safeclaw import __version__
from safeclaw.audit import AuditEvent, read_audit, write_audit
from safeclaw.policy import Policy
from safeclaw.runner import get_registry, run_plan, run_plugin

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_GET_LIMIT = 60  # requests per minute
_POST_LIMIT = 30


class _RateLimiter:
    """Simple in-memory sliding window rate limiter per IP."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = {}

    def is_allowed(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        if key not in self._windows:
            self._windows[key] = deque()
        dq = self._windows[key]
        while dq and dq[0] < now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


_rate_limiter = _RateLimiter()


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "img-src 'self' data:"
    ),
}

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


def _esc(value: object) -> str:
    """Escape a value for safe insertion into HTML."""
    return _html.escape(str(value))


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


def create_app(policy: Policy, *, golden: bool = False) -> FastAPI:
    """Create and return the FastAPI dashboard application."""
    app = FastAPI(title="SafeClaw Dashboard", docs_url=None, redoc_url=None)
    token = get_or_create_token(policy.root_path())
    _golden_mode = golden

    # --- Rate limiting middleware ---
    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # type: ignore[override]
            if request.url.path == "/health":
                return await call_next(request)
            client_ip = request.client.host if request.client else "unknown"
            limit = _POST_LIMIT if request.method == "POST" else _GET_LIMIT
            key = f"{client_ip}:{request.method}"
            if not _rate_limiter.is_allowed(key, limit):
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            return await call_next(request)

    app.add_middleware(RateLimitMiddleware)

    # --- Security headers middleware ---
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # type: ignore[override]
            response = await call_next(request)
            for header, value in _SECURITY_HEADERS.items():
                response.headers[header] = value
            if request.url.path.startswith("/api/") or request.url.path == "/health":
                response.headers["Cache-Control"] = "no-store"
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # --- Health endpoint (no auth) ---
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    # --- Auth dependency ---
    def require_auth(request: Request) -> None:
        # Accept token via Authorization header OR ?token= query param (for browser access)
        auth = request.headers.get("Authorization", "")
        query_token = request.query_params.get("token", "")
        if auth == f"Bearer {token}" or query_token == token:
            return
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    # --- Routes ---

    @app.get("/", response_class=HTMLResponse, response_model=None)
    def home(request: Request, _auth: None = Depends(require_auth)):
        if _golden_mode:
            return RedirectResponse(url="/golden", status_code=302)
        write_audit(
            policy.root_path(),
            AuditEvent(action="dashboard", status="ok", detail="GET /"),
        )
        template_path = Path(__file__).parent / "templates" / "dashboard.html"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        # Fallback to basic inline HTML if template missing
        entries = read_audit(policy.root_path(), last_n=10)
        rows = ""
        for e in entries:
            ts = _esc(e.get("timestamp", "?")[:19])
            cls = "ok" if e.get("status") == "ok" else "error"
            rows += (
                f"<tr><td>{ts}</td><td>{_esc(e.get('action', '?'))}</td>"
                f'<td class="{cls}">{_esc(e.get("status", "?"))}</td>'
                f"<td>{_esc(e.get('detail', '')[:80])}</td></tr>"
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
            ts = _esc(e.get("timestamp", "?")[:19])
            cls = "ok" if e.get("status") == "ok" else "error"
            rows += (
                f"<tr><td>{ts}</td><td>{_esc(e.get('action', '?'))}</td>"
                f'<td class="{cls}">{_esc(e.get("status", "?"))}</td>'
                f"<td>{_esc(e.get('detail', '')[:100])}</td></tr>"
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
        body = f"<pre>{_esc(formatted)}</pre>"
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
            rows += f'<tr><td>{_esc(name)}</td><td class="{cls}">{badge}</td><td>{_esc(doc)}</td></tr>'

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

    # ------------------------------------------------------------------
    # JSON API endpoints (for Golden dashboard)
    # ------------------------------------------------------------------

    @app.get("/api/status")
    def api_status(request: Request, _auth: None = Depends(require_auth)) -> dict[str, Any]:
        entries = read_audit(policy.root_path(), last_n=1000)
        total = len(entries)
        denied = sum(1 for e in entries if e.get("status") == "denied")
        last_entry = entries[0] if entries else None
        return {
            "project_root": str(policy.root_path()),
            "plugins_active": len(policy.allowed_plugins),
            "plugins_total": len(get_registry()),
            "network": policy.allow_network,
            "shell": policy.allow_shell,
            "planner_enabled": policy.planner.enabled,
            "dashboard_enabled": policy.dashboard.enabled,
            "total_scans": total,
            "denied_count": denied,
            "last_entry": last_entry,
            "uptime": time.monotonic(),
        }

    @app.get("/api/audit")
    def api_audit(
        request: Request,
        page: int = 1,
        limit: int = 20,
        status: str = "all",
        search: str = "",
        _auth: None = Depends(require_auth),
    ) -> dict[str, Any]:
        all_entries = read_audit(policy.root_path(), last_n=1000)
        if status != "all":
            all_entries = [e for e in all_entries if e.get("status") == status]
        if search:
            q = search.lower()
            all_entries = [
                e
                for e in all_entries
                if q in e.get("action", "").lower()
                or q in e.get("detail", "").lower()
                or q in e.get("status", "").lower()
            ]
        total = len(all_entries)
        start = (page - 1) * limit
        page_entries = all_entries[start : start + limit]
        return {
            "entries": page_entries,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1,
        }

    @app.get("/api/plugins")
    def api_plugins(request: Request, _auth: None = Depends(require_auth)) -> list[dict[str, Any]]:
        registry = get_registry()
        result = []
        for name in sorted(registry):
            doc = (registry[name].__doc__ or "").split("\n")[0]
            result.append(
                {
                    "name": name,
                    "allowed": name in policy.allowed_plugins,
                    "description": doc,
                }
            )
        return result

    @app.get("/api/policy")
    def api_policy(request: Request, _auth: None = Depends(require_auth)) -> dict[str, Any]:
        return policy.model_dump()

    @app.post("/api/scan")
    def api_scan(
        body: RunRequest,
        request: Request,
        _auth: None = Depends(require_auth),
    ) -> dict[str, Any]:
        if body.plugin not in policy.allowed_plugins:
            raise HTTPException(
                status_code=403,
                detail=f"Plugin '{body.plugin}' is not allowed by policy",
            )
        result = run_plugin(policy, body.plugin, body.target)
        return {"ok": result.ok, "message": result.message, "touched_files": result.touched_files}

    @app.post("/api/plan")
    def api_plan(
        body: PlanRequest,
        request: Request,
        _auth: None = Depends(require_auth),
    ) -> dict[str, Any]:
        from safeclaw.planner import Planner, PlannerError, validate_plan

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

    @app.post("/api/plan/execute")
    def api_plan_execute(
        body: PlanRequest,
        request: Request,
        _auth: None = Depends(require_auth),
    ) -> dict[str, Any]:
        from safeclaw.planner import Planner, PlannerError, validate_plan

        try:
            planner = Planner(policy)
            plan = planner.plan(body.task)
            result = validate_plan(plan, policy)
            if not result.validated:
                return {
                    "executed": False,
                    "reason": "Plan validation failed",
                    "rejected_steps": result.rejected_steps,
                    "results": [],
                }
            results = run_plan(policy, plan)
            return {
                "executed": True,
                "results": [
                    {"plugin": s.plugin, "ok": r.ok, "message": r.message}
                    for s, r in zip(plan.steps, results, strict=False)
                ],
            }
        except PlannerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Golden dashboard route
    # ------------------------------------------------------------------

    @app.get("/golden", response_class=HTMLResponse)
    def golden_page(request: Request, _auth: None = Depends(require_auth)) -> str:
        template_path = Path(__file__).parent / "templates" / "golden.html"
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Golden dashboard template not found")
        return template_path.read_text(encoding="utf-8")

    return app
