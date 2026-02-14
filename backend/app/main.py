from __future__ import annotations

import asyncio
import os
import time
from typing import Dict, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request

from . import audit
from .auth import get_admin_password, make_token, require_auth
from .docker_ops import (
    action_on_containers,
    discover_containers,
    get_container_info,
    tail_logs,
)
from .manifest import load_manifest
from .models import (
    ActionResult,
    AppStatus,
    LoginRequest,
    LoginResponse,
    ServerSummary,
    UrlCheck,
)
from .system_ops import caddy_status, docker_status, read_cpu_percent, read_disk_usage, read_loadavg, read_meminfo, read_uptime_seconds


REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "3"))
TOKEN_EXPIRES_SECONDS = int(os.getenv("TOKEN_EXPIRES_SECONDS", str(8 * 60 * 60)))

app = FastAPI(title="Dashboard v1", version="1.0.0")

# In-memory, per-app action limiter: max 3 actions per app per 5 minutes.
_rate: Dict[str, list[float]] = {}

@app.on_event("startup")
async def _startup():
    # Create audit DB/schema early (so it's present even before first action).
    audit.init_db()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    if body.password != get_admin_password():
        raise HTTPException(status_code=401, detail="Invalid password")

    token = make_token(os.getenv("JWT_SECRET", ""), "admin", TOKEN_EXPIRES_SECONDS)
    return LoginResponse(token=token, expires_in_seconds=TOKEN_EXPIRES_SECONDS)


@app.get("/api/server/summary", response_model=ServerSummary)
async def server_summary(_: dict = Depends(require_auth)):
    uptime = read_uptime_seconds()
    la1, la5, la15 = read_loadavg()
    cpu = read_cpu_percent()
    ram_total, ram_used, ram_pct = read_meminfo()
    disk_total, disk_used, disk_pct = read_disk_usage()

    docker_ok, docker_notes = docker_status()
    caddy_ok, caddy_notes = caddy_status()

    notes = []
    notes.extend(docker_notes)
    notes.extend(caddy_notes)

    return ServerSummary(
        uptime_seconds=uptime,
        loadavg_1=la1,
        loadavg_5=la5,
        loadavg_15=la15,
        cpu_percent=cpu,
        ram_total_bytes=ram_total,
        ram_used_bytes=ram_used,
        ram_used_percent=ram_pct,
        disk_total_bytes=disk_total,
        disk_used_bytes=disk_used,
        disk_used_percent=disk_pct,
        docker_ok=docker_ok,
        caddy_ok=caddy_ok,
        notes=notes,
    )


async def _check_url(url: Optional[str], method: str = "GET") -> Optional[UrlCheck]:
    if not url:
        return None

    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            if method == "HEAD":
                r = await client.head(url)
                # Some servers block HEAD; fallback to GET if needed.
                if r.status_code >= 400:
                    r = await client.get(url)
            else:
                r = await client.get(url)
            ok = 200 <= r.status_code < 400
            return UrlCheck(ok=ok, status_code=r.status_code)
        except Exception as e:
            return UrlCheck(ok=False, status_code=None, error=str(e))


def _compute_status(container_info, backend_check, frontend_check):
    # Container failure dominates.
    stopped = [c for c in container_info if (not c.exists) or (not c.running)]
    if stopped:
        # Prefer first stopped for reason
        c0 = stopped[0]
        if not c0.exists:
            return "DOWN", f"Container missing ({c0.name})", "Fix container name/stack, then restart app"
        if c0.exit_code is not None:
            return "DOWN", f"Container stopped (exit {c0.exit_code})", "Restart app"
        return "DOWN", "Container stopped", "Restart app"

    if backend_check is not None and not backend_check.ok:
        return "DEGRADED", "Backend health failing", "Check backend logs/health"

    if frontend_check is not None and not frontend_check.ok:
        return "DEGRADED", "Frontend unreachable", "Check frontend/Caddy routing"

    return "HEALTHY", "OK", "No action"


@app.get("/api/apps", response_model=list[AppStatus])
async def list_apps(_: dict = Depends(require_auth)):
    manifest = load_manifest()
    out = []

    for k, a in manifest.items():
        cinfo = get_container_info(a.containers)
        backend_check = await _check_url(a.backend_health_url, method="GET")
        frontend_check = await _check_url(a.frontend_url, method="HEAD")
        overall, reason, rec = _compute_status(cinfo, backend_check, frontend_check)

        out.append(
            AppStatus(
                key=a.key,
                name=a.name,
                domain=a.domain,
                containers=a.containers,
                container_info=cinfo,
                backend_health_url=a.backend_health_url,
                frontend_url=a.frontend_url,
                backend_check=backend_check,
                frontend_check=frontend_check,
                overall_status=overall,
                reason=reason,
                recommendation=rec,
            )
        )

    return out


@app.get("/api/apps/{key}", response_model=AppStatus)
async def get_app(key: str, _: dict = Depends(require_auth)):
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    a = manifest[key]
    cinfo = get_container_info(a.containers)
    backend_check = await _check_url(a.backend_health_url, method="GET")
    frontend_check = await _check_url(a.frontend_url, method="HEAD")
    overall, reason, rec = _compute_status(cinfo, backend_check, frontend_check)

    return AppStatus(
        key=a.key,
        name=a.name,
        domain=a.domain,
        containers=a.containers,
        container_info=cinfo,
        backend_health_url=a.backend_health_url,
        frontend_url=a.frontend_url,
        backend_check=backend_check,
        frontend_check=frontend_check,
        overall_status=overall,
        reason=reason,
        recommendation=rec,
    )


@app.get("/api/apps/{key}/logs")
async def app_logs(
    key: str,
    lines: int = Query(200, ge=10, le=5000),
    container: Optional[str] = None,
    _: dict = Depends(require_auth),
):
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    a = manifest[key]
    target = container or (a.containers[0] if a.containers else None)
    if not target:
        raise HTTPException(status_code=400, detail="No containers configured")

    if target not in set(a.containers):
        raise HTTPException(status_code=403, detail="Container not allowlisted for this app")

    try:
        text = tail_logs(target, lines)
        return {"container": target, "lines": lines, "log": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/discover")
async def discover(_: dict = Depends(require_auth)):
    return {"containers": [c.model_dump() for c in discover_containers()]}


def _rate_limit_or_raise(app_key: str):
    now = time.time()
    window = 5 * 60
    max_actions = 3
    lst = _rate.get(app_key, [])
    lst = [t for t in lst if now - t < window]
    if len(lst) >= max_actions:
        raise HTTPException(status_code=429, detail="Rate limit: max 3 actions per app per 5 minutes")
    lst.append(now)
    _rate[app_key] = lst


async def _do_action(request: Request, key: str, action: str) -> ActionResult:
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    _rate_limit_or_raise(key)

    a = manifest[key]
    actor = getattr(request.state, "actor", "admin")
    client_ip = request.client.host if request.client else "unknown"

    # Special case: if we restart/stop the dashboard frontend container, the HTTP connection can drop
    # because /api is proxied through that same nginx container. For that case, schedule the action
    # in the background and return immediately.
    touches_frontend = "dashboard_frontend" in set(a.containers)
    async_mode = touches_frontend and action in {"stop", "restart"}

    async def _run_and_audit():
        # If we restart/stop the backend container itself, do it last, after we audit.
        containers = list(a.containers)
        tail_self = "dashboard_backend" in containers and action in {"stop", "restart"}
        first = [c for c in containers if (not tail_self) or (c != "dashboard_backend")]

        ok, per, err = await asyncio.to_thread(action_on_containers, action, first)

        audit.log_action(
            app_key=key,
            action=action,
            result="ok" if ok else "error",
            actor=str(actor),
            client_ip=str(client_ip),
            error=err,
        )

        if tail_self:
            # No logging after this, because we might kill ourselves.
            await asyncio.to_thread(action_on_containers, action, ["dashboard_backend"])

    if async_mode:
        asyncio.create_task(_run_and_audit())
        per = {name: "scheduled" for name in a.containers}
        return ActionResult(ok=True, app_key=key, action=action, per_container=per, error=None)

    ok, per, err = await asyncio.to_thread(action_on_containers, action, a.containers)
    audit.log_action(
        app_key=key,
        action=action,
        result="ok" if ok else "error",
        actor=str(actor),
        client_ip=str(client_ip),
        error=err,
    )
    return ActionResult(ok=ok, app_key=key, action=action, per_container=per, error=err)


@app.post("/api/apps/{key}/start", response_model=ActionResult)
async def app_start(request: Request, key: str, _: dict = Depends(require_auth)):
    return await _do_action(request, key, "start")


@app.post("/api/apps/{key}/stop", response_model=ActionResult)
async def app_stop(request: Request, key: str, _: dict = Depends(require_auth)):
    return await _do_action(request, key, "stop")


@app.post("/api/apps/{key}/restart", response_model=ActionResult)
async def app_restart(request: Request, key: str, _: dict = Depends(require_auth)):
    return await _do_action(request, key, "restart")
