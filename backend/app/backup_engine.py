from __future__ import annotations

import glob
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .docker_ops import docker_client, docker_ping
from .manifest import load_manifest, ManifestApp


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
            timeout=2,
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

    def _to_local_path(self, host_path: str) -> str:
        """
        Maps a host-side path (e.g. /home/munaim/srv/...) to a local path (e.g. /host/home/munaim/srv/...)
        """
        if not host_path:
            return ""
        if host_path.startswith(HOST_ROOT):
             return host_path
        return os.path.join(HOST_ROOT, host_path.lstrip("/"))

    def _resolve_app_folder(self, app: ManifestApp) -> str:
        # manifest.py now provides a default folder like /home/munaim/srv/apps/<key>
        return app.folder or f"/home/munaim/srv/apps/{app.key}"

    def _get_running_containers_map(self) -> Dict[str, Any]:
        """
        Returns a map of container name -> container object
        """
        c = docker_client()
        out = {}
        try:
            for cont in c.containers.list(all=True):
                # Standard name
                name = cont.name
                out[name] = cont
                # Cleaned name
                name_clean = name.lstrip("/")
                if name_clean != name:
                    out[name_clean] = cont
        except Exception:
            pass
        return out

    def _extract_container_info(self, cont: Any) -> Dict[str, Any]:
        attrs = cont.attrs or {}
        state = attrs.get("State") or {}
        cfg = attrs.get("Config") or {}

        image = ""
        try:
             image = str(cont.image.tags[0] if cont.image.tags else cont.image.short_id)
        except Exception:
             image = str(cfg.get("Image") or "")

        labels = cfg.get("Labels") or {}

        ports = []
        net = attrs.get("NetworkSettings") or {}
        p_map = net.get("Ports") or {}
        if p_map:
            for k in p_map.keys():
                ports.append(k)

        return {
            "name": (attrs.get("Name") or "").lstrip("/") or cont.name,
            "status": str(state.get("Status") or cont.status or "unknown"),
            "ports": ports,
            "image": image,
            "compose_project": labels.get("com.docker.compose.project"),
            "compose_service": labels.get("com.docker.compose.service"),
            "exit_code": state.get("ExitCode")
        }

    def validate_environment(self, estimated_mb: float = 0.0) -> Dict[str, Any]:
        issues: List[str] = []

        if not docker_ping():
            issues.append("Docker not reachable (docker socket ping failed)")

        local_ops = self._to_local_path(HOST_OPS_ROOT)
        ops_exists = os.path.isdir(local_ops)
        if not ops_exists:
            issues.append(f"Missing ops directory: {HOST_OPS_ROOT}")

        try:
            probe_path = local_ops if ops_exists else HOST_ROOT
            du = shutil.disk_usage(probe_path)
            free_mb = du.free / (1024 * 1024)
            required_mb = estimated_mb * 1.2
            if free_mb <= required_mb:
                issues.append(f"Insufficient disk space: free {int(free_mb)}MB, need > {int(required_mb)}MB")
        except Exception as e:
            issues.append(f"Disk space check failed: {e}")

        return {"ready": len(issues) == 0, "issues": issues}

    def generate_plan(self) -> Dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        apps_map = load_manifest()

        inventory = []

        # Summary counters
        total_apps = 0
        total_db_containers = 0
        total_media_paths = 0
        total_est_mb = 0.0

        all_running = self._get_running_containers_map()

        for key, app in sorted(apps_map.items()):
            total_apps += 1

            # 1. Folder Resolution
            folder = self._resolve_app_folder(app)
            local_folder = self._to_local_path(folder)
            folder_exists = os.path.isdir(local_folder)

            app_est_mb = 0.0
            app_issues = []

            # 2. Running Containers
            running_list = []
            for c_name in app.containers:
                if c_name in all_running:
                    cont = all_running[c_name]
                    running_list.append(self._extract_container_info(cont))

            # 3. Required Containers
            required_list = []
            # Use manifest.required_containers (which already has defaults from manifest.py)
            for r_name in sorted(app.required_containers):
                status = "unknown"
                role = "app"
                if "db" in r_name.lower():
                    role = "db"
                elif "worker" in r_name.lower():
                    role = "worker"
                elif "proxy" in r_name.lower() or "caddy" in r_name.lower():
                    role = "proxy"

                is_missing = True
                exit_code = None
                image = ""

                if r_name in all_running:
                    is_missing = False
                    cont = all_running[r_name]
                    info = self._extract_container_info(cont)
                    status = info["status"]
                    exit_code = info["exit_code"]
                    image = info["image"]
                    
                    # Double check role if it's db
                    if "postgres" in image.lower() and role != "db":
                        role = "db"

                required_list.append({
                    "name": r_name,
                    "status": status,
                    "role": role,
                    "missing": is_missing,
                    "image": image,
                    "exit_code": exit_code
                })

                if role == "db":
                    total_db_containers += 1

            # 4. Media Detection
            media_list = []
            potential_media = [
                os.path.join(folder, "media"),
                os.path.join(folder, "uploads")
            ]

            for m_path in potential_media:
                local_m_path = self._to_local_path(m_path)
                exists = os.path.isdir(local_m_path)
                size_mb = None
                warning = None

                if exists:
                    size_mb = _estimate_dir_mb(local_m_path)
                    if size_mb is None:
                        warning = "size estimation timed out"
                    else:
                        app_est_mb += size_mb
                        total_media_paths += 1

                media_list.append({
                    "path": m_path,
                    "exists": exists,
                    "size_mb": size_mb,
                    "warning": warning
                })

            # 5. Config Detection
            configs_list = []
            patterns = [
                "docker-compose*.yml",
                "docker-compose*.yaml",
                "compose*.yml",
                "compose*.yaml",
                ".env"
            ]

            config_paths = set()
            for pat in patterns:
                for p in glob.glob(os.path.join(local_folder, pat)):
                    # Convert back to host path for display
                    h_path = p.replace(HOST_ROOT, "").replace("//", "/")
                    config_paths.add(h_path)

            if app.key == "dashboard":
                config_paths.add(HOST_CADDYFILE)
                # manifest files
                config_paths.add("/home/munaim/srv/apps/dashboard/manifest.yml")
                config_paths.add("/home/munaim/srv/apps/dashboard/data/manifest.override.yml")

            for h_p in sorted(config_paths):
                l_p = self._to_local_path(h_p)
                exists = os.path.exists(l_p)
                size_kb = None
                if exists:
                    try:
                        size_b = os.path.getsize(l_p)
                        size_kb = round(size_b / 1024.0, 2)
                        app_est_mb += (size_b / (1024.0 * 1024.0))
                    except:
                        pass

                configs_list.append({
                    "path": h_p,
                    "exists": exists,
                    "size_kb": size_kb
                })

            # 6. Status Computation
            # READY|WARNING|MISSING
            status = "READY"
            if not folder_exists:
                status = "MISSING"
                app_issues.append("Folder missing")

            for req in required_list:
                if req["missing"]:
                    status = "MISSING"
                    app_issues.append(f"Required container missing: {req['name']}")
                elif req["status"] != "running":
                    if status != "MISSING":
                        status = "WARNING"
                    app_issues.append(f"Required container not running: {req['name']} ({req['status']})")

            # Final inventory item
            inventory.append({
                "key": app.key,
                "name": app.name,
                "domain": app.domain,
                "folder": folder,
                "folder_exists": folder_exists,
                "running_containers": running_list,
                "required_containers": required_list,
                "media": media_list,
                "configs": configs_list,
                "estimated_app_total_mb": round(app_est_mb, 2),
                "status": status,
                "issues": app_issues
            })
            total_est_mb += app_est_mb

        summary = {
            "apps_count": total_apps,
            "db_containers_count": total_db_containers,
            "media_paths_count": total_media_paths,
            "estimated_total_mb": round(total_est_mb, 2),
            "estimated_total_gb": round(total_est_mb / 1024.0, 3)
        }
        validation = self.validate_environment(summary["estimated_total_mb"])
        summary["ready"] = validation["ready"]
        summary["issues"] = validation["issues"]

        return {
            "timestamp": ts,
            "summary": summary,
            "applications": inventory
        }
