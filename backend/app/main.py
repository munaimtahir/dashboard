from __future__ import annotations

import asyncio
import os
import re
import time
from urllib.parse import urlparse
from typing import Dict, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Header
from fastapi.responses import PlainTextResponse
from docker.errors import NotFound as DockerNotFound

from . import audit
from .auth import get_admin_password, make_token, require_auth
from .docker_ops import (
    action_on_containers,
    discover_inventory,
    get_container_info,
    list_container_names,
    tail_logs,
)
from .backup_engine import BackupEngine
from .failure_intel import evaluate as eval_failure
from .manifest import clear_cache as clear_manifest_cache
from .manifest import load_manifest, load_manifest_raw, upsert_override_app, OVERRIDE_MANIFEST_PATH
from .models import (
    ActionResponse,
    AppStatus,
    ManifestResponse,
    ManifestUpsertRequest,
    LoginRequest,
    LoginResponse,
    ServerSummary,
    UrlCheck,
    InventoryPreviewResponse,
    InventorySyncResponse,
    OpsStatusResponse,
    OpsActionResponse,
)
from .system_ops import caddy_status, docker_status, read_cpu_percent, read_disk_usage, read_loadavg, read_meminfo, read_uptime_seconds
from .inventory_sync import scan_inventory, write_manifest_override
from .app_ops import execute_ops_action, get_ops_status, OpsError


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

async def _build_app_status(a) -> AppStatus:
    cinfo = get_container_info(a.containers)
    backend_check = await _check_url(a.backend_health_url, method="GET")
    frontend_check = await _check_url(a.frontend_url, method="HEAD")
    overall, failure_category, reason, rec, evidence, last_log_snippet = eval_failure(
        containers=list(a.containers),
        container_info=cinfo,
        backend_check=backend_check,
        frontend_check=frontend_check,
    )

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
        failure_category=failure_category,
        reason=reason,
        recommendation=rec,
        recommended_action=rec,
        evidence=evidence or {},
        last_log_snippet=last_log_snippet,
    )


@app.get("/api/apps", response_model=list[AppStatus])
async def list_apps(_: dict = Depends(require_auth)):
    manifest = load_manifest()
    out = []

    for k, a in manifest.items():
        out.append(await _build_app_status(a))

    return out


@app.get("/api/apps/{key}", response_model=AppStatus)
async def get_app(key: str, _: dict = Depends(require_auth)):
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    a = manifest[key]
    return await _build_app_status(a)


@app.get("/api/apps/{key}/logs")
async def app_logs(
    key: str,
    lines: int = Query(200, ge=1, le=500),
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
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
    except DockerNotFound:
        raise HTTPException(
            status_code=404,
            detail={"error": "container_not_found", "container": target, "app_key": key},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "logs_failed", "message": str(e), "container": target, "app_key": key},
        )


@app.get("/api/discover")
async def discover(
    project: Optional[str] = None,
    contains: Optional[str] = None,
    _: dict = Depends(require_auth),
):
    inv = discover_inventory(project=project, contains=contains)
    return inv.model_dump()


def _validate_key(key: str):
    if not (2 <= len(key) <= 32):
        raise HTTPException(status_code=422, detail="key length must be 2–32")
    if not re.fullmatch(r"[a-z0-9_-]+", key):
        raise HTTPException(status_code=422, detail="key must match [a-z0-9_-]+")


def _validate_url(u: Optional[str], field: str):
    if not u:
        return
    try:
        p = urlparse(u)
        if p.scheme not in {"http", "https"}:
            raise ValueError("scheme must be http(s)")
        if not p.netloc:
            raise ValueError("missing host")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"{field} invalid: {e}")


@app.get("/api/manifest", response_model=ManifestResponse)
async def get_manifest(_: dict = Depends(require_auth)):
    return load_manifest_raw()


@app.post("/api/manifest/apps", response_model=ManifestResponse)
async def upsert_manifest_app(body: ManifestUpsertRequest, _: dict = Depends(require_auth)):
    key = body.key.strip()
    _validate_key(key)
    _validate_url(body.backend_health_url, "backend_health_url")
    _validate_url(body.frontend_url, "frontend_url")

    if not body.containers:
        raise HTTPException(status_code=422, detail="containers required")

    if not body.allow_missing_containers:
        existing = list_container_names()
        missing = [c for c in body.containers if c not in existing]
        if missing:
            raise HTTPException(status_code=422, detail={"error": "missing_containers", "missing": missing})

    merged = upsert_override_app(body.model_dump(exclude={"allow_missing_containers"}))
    return merged


@app.post("/api/manifest/reload")
async def reload_manifest(_: dict = Depends(require_auth)):
    clear_manifest_cache()
    return {"ok": True}


@app.get("/api/backups/plan")
async def backups_plan(_: dict = Depends(require_auth)):
    eng = BackupEngine()
    return eng.generate_plan()


@app.get("/api/backups/validate")
async def backups_validate(_: dict = Depends(require_auth)):
    eng = BackupEngine()
    plan = eng.generate_plan()
    return plan["summary"]


@app.post("/api/backups/simulate")
async def backups_simulate(_: dict = Depends(require_auth)):
    eng = BackupEngine()
    plan = eng.generate_plan()
    return {"message": "Simulation successful. No files created.", "plan": plan}


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


def _client_ip(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").strip()
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def _do_action(request: Request, key: str, action: str) -> ActionResponse:
    manifest = load_manifest()
    if key not in manifest:
        audit.log_action(
            app_key=key,
            action=action,
            result="fail",
            exit_code=None,
            message="Unknown app key",
            client_ip=_client_ip(request),
        )
        raise HTTPException(status_code=404, detail="Unknown app key")

    a = manifest[key]
    client_ip = _client_ip(request)

    try:
        _rate_limit_or_raise(key)
    except HTTPException as e:
        if e.status_code == 429:
            audit.log_action(
                app_key=key,
                action=action,
                result="fail",
                exit_code=None,
                message=str(e.detail),
                client_ip=client_ip,
            )
        raise

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
            result="success" if ok else "fail",
            exit_code=0 if ok else 1,
            message=(err or ""),
            client_ip=str(client_ip),
        )

        if tail_self:
            # No logging after this, because we might kill ourselves.
            await asyncio.to_thread(action_on_containers, action, ["dashboard_backend"])

    if async_mode:
        asyncio.create_task(_run_and_audit())
        per = {name: "scheduled" for name in a.containers}
        return ActionResponse(
            ok=True,
            app_key=key,
            action=action,
            per_container=per,
            exit_code=0,
            message="scheduled",
            status=await _build_app_status(a),
        )

    ok, per, err = await asyncio.to_thread(action_on_containers, action, a.containers)
    audit.log_action(
        app_key=key,
        action=action,
        result="success" if ok else "fail",
        exit_code=0 if ok else 1,
        message=(err or ""),
        client_ip=str(client_ip),
    )
    return ActionResponse(
        ok=ok,
        app_key=key,
        action=action,
        per_container=per,
        exit_code=0 if ok else 1,
        message=(err or "ok"),
        status=await _build_app_status(a),
    )


@app.post("/api/apps/{key}/start", response_model=ActionResponse)
async def app_start(request: Request, key: str, _: dict = Depends(require_auth)):
    return await _do_action(request, key, "start")


@app.post("/api/apps/{key}/stop", response_model=ActionResponse)
async def app_stop(request: Request, key: str, _: dict = Depends(require_auth)):
    return await _do_action(request, key, "stop")


@app.post("/api/apps/{key}/restart", response_model=ActionResponse)
async def app_restart(request: Request, key: str, _: dict = Depends(require_auth)):
    return await _do_action(request, key, "restart")


# ============================================================================
# INVENTORY SYNC ENDPOINTS
# ============================================================================

@app.post("/api/inventory/preview", response_model=InventoryPreviewResponse)
async def inventory_preview(_: dict = Depends(require_auth)):
    """
    Preview inventory sync changes without writing to disk.
    Shows what apps would be added/removed/updated.
    """
    # Load existing override manifest
    existing_manifest = None
    if os.path.exists(OVERRIDE_MANIFEST_PATH):
        import yaml
        with open(OVERRIDE_MANIFEST_PATH, "r", encoding="utf-8") as f:
            existing_manifest = yaml.safe_load(f) or {}

    # Scan inventory
    result = scan_inventory(existing_manifest)

    return InventoryPreviewResponse(
        summary={
            "added": result.added,
            "removed": result.removed,
            "updated": result.updated,
            "skipped_folders": result.skipped_folders,
        },
        preview_manifest=result.preview_manifest,
    )


@app.post("/api/inventory/sync", response_model=InventorySyncResponse)
async def inventory_sync(_: dict = Depends(require_auth)):
    """
    Perform inventory sync and write to manifest.override.yml.
    Returns summary of changes and new manifest.
    """
    # Load existing override manifest
    existing_manifest = None
    if os.path.exists(OVERRIDE_MANIFEST_PATH):
        import yaml
        with open(OVERRIDE_MANIFEST_PATH, "r", encoding="utf-8") as f:
            existing_manifest = yaml.safe_load(f) or {}

    # Scan inventory
    result = scan_inventory(existing_manifest)

    # Write to disk
    write_manifest_override(result.preview_manifest, OVERRIDE_MANIFEST_PATH)

    # Clear cache to reload
    clear_manifest_cache()

    # Return new merged manifest
    new_manifest = load_manifest_raw()

    return InventorySyncResponse(
        summary={
            "added": result.added,
            "removed": result.removed,
            "updated": result.updated,
            "skipped_folders": result.skipped_folders,
        },
        manifest=new_manifest,
    )


# ============================================================================
# OPS ENDPOINTS
# ============================================================================

@app.get("/api/apps/{key}/ops/status", response_model=OpsStatusResponse)
async def ops_status(key: str, _: dict = Depends(require_auth)):
    """Get ops configuration status for an app"""
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    app = manifest[key]
    status = get_ops_status(key, app.folder)

    return OpsStatusResponse(**status)


async def _execute_ops_and_audit(
    request: Request,
    key: str,
    action: str,
    confirm_header: Optional[str] = None,
) -> OpsActionResponse:
    """Execute ops action and audit the result"""
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    app = manifest[key]
    client_ip = _client_ip(request)

    try:
        # Execute ops action
        result = execute_ops_action(
            app_key=key,
            app_folder=app.folder,
            action=action,
            confirm_header=confirm_header,
        )

        # Audit the action
        audit.log_action(
            app_key=key,
            action=f"ops:{action}",
            result="success" if result.success else "fail",
            exit_code=result.exit_code,
            message=result.message,
            client_ip=client_ip,
        )

        # Get updated app status
        updated_status = await _build_app_status(app)

        return OpsActionResponse(
            success=result.success,
            exit_code=result.exit_code,
            log_file=result.log_file,
            tail=result.tail,
            message=result.message,
            updated_app_status=updated_status,
        )

    except OpsError as e:
        # Audit the failure
        audit.log_action(
            app_key=key,
            action=f"ops:{action}",
            result="fail",
            exit_code=None,
            message=e.message,
            client_ip=client_ip,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.post("/api/apps/{key}/ops/start", response_model=OpsActionResponse)
async def ops_start(request: Request, key: str, _: dict = Depends(require_auth)):
    """Execute start ops script for an app"""
    return await _execute_ops_and_audit(request, key, "start")


@app.post("/api/apps/{key}/ops/stop", response_model=OpsActionResponse)
async def ops_stop(request: Request, key: str, _: dict = Depends(require_auth)):
    """Execute stop ops script for an app"""
    return await _execute_ops_and_audit(request, key, "stop")


@app.post("/api/apps/{key}/ops/restart", response_model=OpsActionResponse)
async def ops_restart(request: Request, key: str, _: dict = Depends(require_auth)):
    """Execute restart ops script for an app"""
    return await _execute_ops_and_audit(request, key, "restart")


@app.post("/api/apps/{key}/ops/deploy", response_model=OpsActionResponse)
async def ops_deploy(
    request: Request,
    key: str,
    x_confirm: Optional[str] = Header(None),
    _: dict = Depends(require_auth),
):
    """
    Execute deploy ops script for an app.
    Requires confirmation header: X-Confirm: DEPLOY <key>
    Rate limited: 1 per app per 10 minutes.
    """
    return await _execute_ops_and_audit(request, key, "deploy", confirm_header=x_confirm)


@app.get("/api/apps/{key}/ops/logs")
async def ops_logs(
    key: str,
    lines: int = Query(200, ge=1, le=1000),
    _: dict = Depends(require_auth),
):
    """
    Get ops logs for the most recent operation.
    Returns plain text log content.
    """
    manifest = load_manifest()
    if key not in manifest:
        raise HTTPException(status_code=404, detail="Unknown app key")

    # Find most recent log file for this app
    from pathlib import Path
    from .app_ops import OPS_LOGS_DIR

    logs_dir = Path(OPS_LOGS_DIR)
    if not logs_dir.exists():
        raise HTTPException(status_code=404, detail="No ops logs found")

    # Find log files for this app
    log_files = sorted(
        [f for f in logs_dir.glob(f"{key}_*.log")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not log_files:
        raise HTTPException(status_code=404, detail="No ops logs found for this app")

    # Read most recent log
    log_file = log_files[0]
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:]
            content = "".join(tail_lines)
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {str(e)}")


@app.get("/api/audit/logs")
async def audit_logs(limit: int = Query(50, ge=1, le=200), _: dict = Depends(require_auth)):
    return audit.list_recent_actions(limit)

