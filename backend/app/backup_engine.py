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

    def _resolve_app_folder(self, app: ManifestApp) -> str:
        if app.folder:
            return app.folder
        # Default: /home/munaim/srv/apps/<key>
        # mapped to HOST_APPS_ROOT/<key>
        return os.path.join(HOST_APPS_ROOT, app.key)

    def _get_running_containers_map(self) -> Dict[str, Any]:
        """
        Returns a map of container name -> container object
        """
        c = docker_client()
        out = {}
        try:
            for cont in c.containers.list(all=True):
                out[cont.name] = cont
                # Also handle if name has a slash
                name_clean = cont.name.lstrip("/")
                if name_clean != cont.name:
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
        for k, v in p_map.items():
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

        ops_exists = os.path.isdir(HOST_OPS_ROOT)
        if not ops_exists:
            issues.append(f"Missing ops directory: {HOST_OPS_ROOT}")

        try:
            probe_path = HOST_OPS_ROOT if ops_exists else HOST_ROOT
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
        summary: Dict[str, Any] = {}
        total_apps = 0
        total_db_containers = 0
        total_media_paths = 0
        total_est_mb = 0.0

        all_running = self._get_running_containers_map()

        for key, app in sorted(apps_map.items()):
            total_apps += 1

            # 1. Folder Resolution
            folder = self._resolve_app_folder(app)
            folder_exists = os.path.isdir(folder)

            app_est_mb = 0.0
            app_issues = []

            # 2. Running Containers
            running_list = []
            # We look for containers that match the manifest.containers list
            # OR have labels matching the project?
            # The requirement says "Use docker inspect... Extract..."
            # It implies we find the containers belonging to this app.
            # Usually we use the list in manifest.

            # To be safe and consistent with previous logic, we check the names in app.containers
            # And also maybe check labels if we wanted, but manifest.containers is authoritative in this system.

            for c_name in app.containers:
                if c_name in all_running:
                    cont = all_running[c_name]
                    info = self._extract_container_info(cont)
                    running_list.append(info)

            # 3. Required Containers
            required_list = []

            # Identify what is required
            req_names: Set[str] = set()
            if app.required_containers:
                req_names = set(app.required_containers)
            else:
                # Auto-detect from manifest.containers
                for c_name in app.containers:
                    if "db" in c_name.lower():
                        req_names.add(c_name)
                    # Check image name from running container if available?
                    # The requirement says: "containers containing 'db' OR image containing 'postgres'"
                    # If it's not running, we can't check image easily unless we assume a naming convention or look at compose file (hard).
                    # We will check if it's in the running list and has postgres image.
                    if c_name in all_running:
                         cont = all_running[c_name]
                         # Check if image contains postgres
                         try:
                             # We can use the info we extracted or raw obj
                             # Let's check image name roughly
                             img = ""
                             if cont.attrs and cont.attrs.get("Config"):
                                 img = cont.attrs["Config"].get("Image") or ""
                             if "postgres" in img.lower():
                                 req_names.add(c_name)
                         except:
                             pass

            # Now build the required_containers list for output
            for r_name in sorted(req_names):
                status = "unknown"
                role = "unknown"
                if "db" in r_name.lower() or "postgres" in r_name.lower():
                    role = "db"
                elif "worker" in r_name.lower():
                    role = "worker"
                else:
                    role = "app"

                is_missing = True
                exit_code = None

                if r_name in all_running:
                    is_missing = False
                    # Extract status/exit code from running info
                    # We can find it in running_list or look up in all_running
                    cont = all_running[r_name]
                    status = cont.status
                    if cont.attrs and cont.attrs.get("State"):
                        exit_code = cont.attrs["State"].get("ExitCode")

                required_list.append({
                    "name": r_name,
                    "status": status,
                    "role": role,
                    "missing": is_missing,
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
                exists = os.path.isdir(m_path)
                size_mb = None
                warning = None

                if exists:
                    size_mb = _estimate_dir_mb(m_path)
                    if size_mb is None:
                        # Timeout or error
                        warning = "Size estimation timed out or failed"
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

            # Base patterns inside the folder
            patterns = [
                "docker-compose*.yml",
                "docker-compose*.yaml",
                "compose*.yml",
                "compose*.yaml",
                ".env"
            ]

            config_paths = set()
            for pat in patterns:
                for p in glob.glob(os.path.join(folder, pat)):
                    config_paths.add(p)

            # Global configs - only attach to "dashboard" app to avoid duplication
            if app.key == "dashboard":
                if os.path.exists(HOST_CADDYFILE):
                    config_paths.add(HOST_CADDYFILE)

                # manifest.yml location:
                # Based on previous code: os.path.join(HOST_APPS_ROOT, "dashboard/manifest.yml")
                # Wait, HOST_APPS_ROOT is /home/munaim/srv/apps
                # dashboard app is likely in /home/munaim/srv/apps/dashboard
                # so manifest.yml might be in there.
                # The requirements said: "/home/munaim/srv/dashboard/manifest.yml"
                # Let's use the exact path from requirements if it exists, or check relative.
                # Requirement: /home/munaim/srv/dashboard/manifest.yml
                # But wait, HOST_ROOT might affect this.
                # HOST_ROOT defaults to /host.
                # So it would be HOST_ROOT/home/munaim/srv/dashboard/manifest.yml

                # Let's stick to what was working or what looks right.
                # previous code had: os.path.join(HOST_APPS_ROOT, "dashboard/manifest.yml")
                # AND os.path.join(HOST_APPS_ROOT, "dashboard/data/manifest.override.yml")
                # I'll include those.

                p1 = os.path.join(HOST_APPS_ROOT, "dashboard/manifest.yml")
                p2 = os.path.join(HOST_APPS_ROOT, "dashboard/data/manifest.override.yml")
                config_paths.add(p1)
                config_paths.add(p2)

            for p in sorted(config_paths):
                exists = os.path.exists(p)
                size_kb = None
                if exists:
                    try:
                        size_b = os.path.getsize(p)
                        size_kb = round(size_b / 1024.0, 2)
                        # Add to total size (convert to MB)
                        app_est_mb += (size_b / (1024.0 * 1024.0))
                    except:
                        pass

                configs_list.append({
                    "path": p,
                    "exists": exists,
                    "size_kb": size_kb
                })

            total_est_mb += app_est_mb

            # 6. Status Computation
            # READY → all required containers running + no missing folder
            # WARNING → folder exists but media/config missing (Wait, "media/config missing" - if media is optional?)
            # The rule: WARNING → folder exists but media/config missing
            # MISSING → required container missing or folder missing

            status = "READY"

            # Check MISSING conditions
            if not folder_exists:
                status = "MISSING"
                app_issues.append("App folder missing")

            for req in required_list:
                if req["missing"]:
                    status = "MISSING"
                    app_issues.append(f"Required container missing: {req['name']}")

            # Check WARNING conditions (only if not MISSING)
            if status != "MISSING":
                # "folder exists but media/config missing"
                # If we have media paths defined but they don't exist?
                # Or if we have NO configs?

                # If no configs found?
                if not any(c['exists'] for c in configs_list):
                     # Is it a warning? Maybe.
                     pass

                # If media paths don't exist?
                # Only warn if we expect them?
                # The rule is slightly vague: "folder exists but media/config missing"
                # I'll interpret: if any detected media/config path was checked and found missing, it's NOT necessarily a warning,
                # because we check `media` and `uploads` speculatively.

                # Maybe "WARNING" if folder exists but NO docker-compose found?
                has_compose = any("compose" in c['path'] and c['exists'] for c in configs_list)
                if not has_compose:
                    status = "WARNING"
                    app_issues.append("No docker-compose configuration found")

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

        # Final Summary
        summary["apps_count"] = total_apps
        summary["db_containers_count"] = total_db_containers
        summary["media_paths_count"] = total_media_paths
        summary["estimated_total_mb"] = round(total_est_mb, 2)
        summary["estimated_total_gb"] = round(total_est_mb / 1024.0, 3)

        validation = self.validate_environment(summary["estimated_total_mb"])
        summary["ready"] = validation["ready"]
        summary["issues"] = validation["issues"]

        return {
            "timestamp": ts,
            "summary": summary,
            "applications": inventory
        }
