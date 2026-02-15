from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


BASE_MANIFEST_PATH = os.getenv("MANIFEST_PATH", "/app/manifest.yml")
OVERRIDE_MANIFEST_PATH = os.getenv("MANIFEST_OVERRIDE_PATH", "/data/manifest.override.yml")

_lock = threading.RLock()
_cache: Optional[Dict[str, Any]] = None
_cache_mtime: tuple[float, float] | None = None


@dataclass
class ManifestApp:
    key: str
    name: str
    domain: Optional[str]
    folder: Optional[str]
    containers: List[str]
    required_containers: List[str]
    backend_health_url: Optional[str]
    frontend_url: Optional[str]


def _read_yaml(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _normalize_apps(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in (data.get("apps") or []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        out[key] = {
            "key": key,
            "name": str(item.get("name") or key),
            "domain": (str(item.get("domain")).strip() if item.get("domain") else None),
            "folder": (str(item.get("folder")).strip() if item.get("folder") else None),
            "containers": [str(c) for c in (item.get("containers") or [])],
            "required_containers": [str(c) for c in (item.get("required_containers") or [])],
            "backend_health_url": (
                str(item.get("backend_health_url")).strip() if item.get("backend_health_url") else None
            ),
            "frontend_url": (str(item.get("frontend_url")).strip() if item.get("frontend_url") else None),
        }
    return out


def _merged_manifest_raw() -> Dict[str, Any]:
    base = _read_yaml(BASE_MANIFEST_PATH)
    override = _read_yaml(OVERRIDE_MANIFEST_PATH)

    base_apps = _normalize_apps(base)
    override_apps = _normalize_apps(override)

    merged = dict(base_apps)
    merged.update(override_apps)

    apps_list = [merged[k] for k in sorted(merged.keys())]
    return {"apps": apps_list}


def _mtimes() -> tuple[float, float]:
    base_m = os.path.getmtime(BASE_MANIFEST_PATH) if os.path.exists(BASE_MANIFEST_PATH) else 0.0
    over_m = os.path.getmtime(OVERRIDE_MANIFEST_PATH) if os.path.exists(OVERRIDE_MANIFEST_PATH) else 0.0
    return base_m, over_m


def clear_cache():
    global _cache, _cache_mtime
    with _lock:
        _cache = None
        _cache_mtime = None


def load_manifest_raw() -> Dict[str, Any]:
    global _cache, _cache_mtime
    with _lock:
        mt = _mtimes()
        if _cache is not None and _cache_mtime == mt:
            return _cache
        _cache = _merged_manifest_raw()
        _cache_mtime = mt
        return _cache


def load_manifest() -> Dict[str, ManifestApp]:
    data = load_manifest_raw()
    apps: Dict[str, ManifestApp] = {}
    for item in (data.get("apps") or []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        
        # Default folder: /home/munaim/srv/apps/<key>
        folder = str(item.get("folder") or "").strip()
        if not folder:
            folder = f"/home/munaim/srv/apps/{key}"
            
        containers = [str(c) for c in (item.get("containers") or [])]
        
        # Default required_containers
        required_containers = [str(c) for c in (item.get("required_containers") or [])]
        if not required_containers and containers:
            # Logic: any container name containing "db" or first container
            # Image check usually happens in backup_engine, but we can do a name-based check here
            # and let backup_engine supplement it if needed, or just do it all there.
            # However, the requirement says "IF these fields are absent, compute".
            
            db_conts = [c for c in containers if "db" in c.lower()]
            if db_conts:
                required_containers = db_conts
            else:
                required_containers = [containers[0]]

        apps[key] = ManifestApp(
            key=key,
            name=str(item.get("name") or key),
            domain=(str(item.get("domain")).strip() if item.get("domain") else None),
            folder=folder,
            containers=containers,
            required_containers=required_containers,
            backend_health_url=(str(item.get("backend_health_url")).strip() if item.get("backend_health_url") else None),
            frontend_url=(str(item.get("frontend_url")).strip() if item.get("frontend_url") else None),
        )
    return apps


def upsert_override_app(app: Dict[str, Any]) -> Dict[str, Any]:
    key = str(app.get("key") or "").strip()
    if not key:
        raise ValueError("key required")

    with _lock:
        override = _read_yaml(OVERRIDE_MANIFEST_PATH)
        by_key = _normalize_apps(override)
        by_key[key] = {
            "key": key,
            "name": str(app.get("name") or key),
            "domain": (str(app.get("domain")).strip() if app.get("domain") else None),
            "folder": (str(app.get("folder")).strip() if app.get("folder") else None),
            "containers": [str(c) for c in (app.get("containers") or [])],
            "required_containers": [str(c) for c in (app.get("required_containers") or [])],
            "backend_health_url": (str(app.get("backend_health_url")).strip() if app.get("backend_health_url") else None),
            "frontend_url": (str(app.get("frontend_url")).strip() if app.get("frontend_url") else None),
        }

        os.makedirs(os.path.dirname(OVERRIDE_MANIFEST_PATH), exist_ok=True)
        tmp = f"{OVERRIDE_MANIFEST_PATH}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump({"apps": [by_key[k] for k in sorted(by_key.keys())]}, f, sort_keys=False)
        os.replace(tmp, OVERRIDE_MANIFEST_PATH)

        clear_cache()
        return load_manifest_raw()
