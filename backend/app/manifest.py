from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


MANIFEST_PATH = os.getenv("MANIFEST_PATH", "/app/manifest.yml")


@dataclass
class ManifestApp:
    key: str
    name: str
    domain: Optional[str]
    containers: List[str]
    backend_health_url: Optional[str]
    frontend_url: Optional[str]


def load_manifest(path: str = MANIFEST_PATH) -> Dict[str, ManifestApp]:
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    apps = {}
    for item in (data.get("apps") or []):
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        apps[key] = ManifestApp(
            key=key,
            name=str(item.get("name") or key),
            domain=(str(item.get("domain")).strip() if item.get("domain") else None),
            containers=[str(c) for c in (item.get("containers") or [])],
            backend_health_url=(
                str(item.get("backend_health_url")).strip()
                if item.get("backend_health_url")
                else None
            ),
            frontend_url=(
                str(item.get("frontend_url")).strip() if item.get("frontend_url") else None
            ),
        )

    return apps


def allowed_containers_for_app(app: ManifestApp) -> set[str]:
    return set(app.containers)
