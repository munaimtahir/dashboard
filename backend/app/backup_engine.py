from __future__ import annotations

import glob
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .docker_ops import docker_client, docker_ping


HOST_ROOT = os.getenv("HOST_ROOT", "/host")
HOST_APPS_ROOT = os.getenv("HOST_APPS_ROOT", os.path.join(HOST_ROOT, "home/munaim/srv/apps"))
HOST_OPS_ROOT = os.getenv("HOST_OPS_ROOT", os.path.join(HOST_ROOT, "home/munaim/srv/ops"))
HOST_CADDYFILE = os.getenv("HOST_CADDYFILE", os.path.join(HOST_ROOT, "etc/caddy/Caddyfile"))


def _du_sm(path: str) -> Optional[int]:
    try:
        r = subprocess.run(
            ["du", "-sm", "--", path],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return None
        first = (r.stdout or "").strip().splitlines()[0].split()[0]
        return int(first)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _walk_size_mb(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                total += os.path.getsize(fp)
            except Exception:
                continue
    return int((total + (1024 * 1024 - 1)) / (1024 * 1024))


def _estimate_dir_mb(path: str) -> int:
    mb = _du_sm(path)
    if mb is not None:
        return mb
    return _walk_size_mb(path)


def _estimate_file_mb(path: str) -> int:
    try:
        b = os.path.getsize(path)
        return int((b + (1024 * 1024 - 1)) / (1024 * 1024))
    except Exception:
        return 0


class BackupEngine:
    """
    Dry-run only planner. No writes. No pg_dump / tar execution.
    """

    def discover_databases(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        c = docker_client()
        for cont in c.containers.list(all=True):
            try:
                attrs = cont.attrs or {}
                image = ""
                try:
                    image = str(cont.image.tags[0] if cont.image.tags else cont.image.short_id)
                except Exception:
                    image = ""

                cfg = attrs.get("Config") or {}
                img_name = str(cfg.get("Image") or image or "")
                if "postgres" not in img_name.lower():
                    continue

                state = attrs.get("State") or {}
                status = str(state.get("Status") or cont.status or "unknown")
                name = (attrs.get("Name") or "").lstrip("/") or cont.name
                out.append(
                    {
                        "container": name,
                        "image": img_name,
                        "status": status,
                        "would_dump_command": f"docker exec {name} pg_dumpall -U postgres",
                    }
                )
            except Exception:
                continue
        out.sort(key=lambda x: x.get("container") or "")
        return out

    def discover_media(self) -> List[Dict[str, Any]]:
        targets: List[str] = []
        targets.extend(glob.glob(os.path.join(HOST_APPS_ROOT, "*/media")))
        targets.extend(glob.glob(os.path.join(HOST_APPS_ROOT, "*/uploads")))

        out: List[Dict[str, Any]] = []
        for p in sorted(set(targets)):
            exists = os.path.isdir(p)
            est = _estimate_dir_mb(p) if exists else 0
            out.append({"path": p, "exists": exists, "estimated_size_mb": est})
        return out

    def discover_configs(self) -> List[Dict[str, Any]]:
        patterns = [
            os.path.join(HOST_APPS_ROOT, "*/docker-compose*.yml"),
            os.path.join(HOST_APPS_ROOT, "*/docker-compose*.yaml"),
            os.path.join(HOST_APPS_ROOT, "*/compose*.yml"),
            os.path.join(HOST_APPS_ROOT, "*/compose*.yaml"),
            os.path.join(HOST_APPS_ROOT, "*/.env"),
        ]

        paths: set[str] = set()
        for pat in patterns:
            for p in glob.glob(pat):
                paths.add(p)

        paths.add(HOST_CADDYFILE)
        paths.add(os.path.join(HOST_APPS_ROOT, "dashboard/manifest.yml"))
        paths.add(os.path.join(HOST_APPS_ROOT, "dashboard/data/manifest.override.yml"))

        out: List[Dict[str, Any]] = []
        for p in sorted(paths):
            exists = os.path.exists(p)
            est = _estimate_file_mb(p) if exists and os.path.isfile(p) else 0
            out.append({"path": p, "exists": exists, "estimated_size_mb": est})
        return out

    def estimate_total_size(self) -> Dict[str, Any]:
        media = self.discover_media()
        configs = self.discover_configs()
        total_mb = sum(int(x.get("estimated_size_mb") or 0) for x in (media + configs))
        total_gb = round(total_mb / 1024.0, 3)
        return {"estimated_total_mb": total_mb, "estimated_total_gb": total_gb}

    def validate_environment(self) -> Dict[str, Any]:
        issues: List[str] = []

        if not docker_ping():
            issues.append("Docker not reachable (docker socket ping failed)")

        ops_exists = os.path.isdir(HOST_OPS_ROOT)
        if not ops_exists:
            issues.append(f"Missing ops directory: {HOST_OPS_ROOT}")

        est = self.estimate_total_size()
        est_mb = float(est.get("estimated_total_mb") or 0.0)

        try:
            probe_path = HOST_OPS_ROOT if ops_exists else HOST_ROOT
            du = shutil.disk_usage(probe_path)
            free_mb = du.free / (1024 * 1024)
            required_mb = est_mb * 1.2
            if free_mb <= required_mb:
                issues.append(f"Insufficient disk space: free {int(free_mb)}MB, need > {int(required_mb)}MB")
        except Exception as e:
            issues.append(f"Disk space check failed: {e}")

        return {"ready": len(issues) == 0, "issues": issues}

    def generate_plan(self) -> Dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        databases = self.discover_databases()
        media = self.discover_media()
        configs = self.discover_configs()
        est = self.estimate_total_size()
        validation = self.validate_environment()
        return {
            "timestamp": ts,
            "databases": databases,
            "media": media,
            "configs": configs,
            "estimated_total_mb": est["estimated_total_mb"],
            "estimated_total_gb": est["estimated_total_gb"],
            "validation": validation,
            "notes": [
                "Dry run only: no pg_dump or tar executed.",
                "DB dump sizes are not estimated; totals include media + configs only.",
            ],
        }
