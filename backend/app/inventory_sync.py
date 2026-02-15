"""
Inventory Sync Module

Scans the server for real applications and produces a cleaned manifest override.
Implements strict safety rules: no arbitrary commands, only allowlisted operations.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import docker
import yaml


APPS_ROOT = "/home/munaim/srv/apps"
CADDYFILE_PATH = "/home/munaim/srv/proxy/caddy/Caddyfile"
SKIP_PREFIXES = ("test", "tmp", "demo", "sample")


@dataclass
class ScannedApp:
    """Represents a discovered application"""
    key: str
    name: str
    domain: Optional[str]
    folder: str
    containers: List[str]
    required_containers: List[str]
    backend_health_url: Optional[str]
    frontend_url: Optional[str]


@dataclass
class InventorySyncResult:
    """Result of inventory sync operation"""
    added: List[str]
    removed: List[str]
    updated: List[str]
    skipped_folders: List[str]
    preview_manifest: Dict


def _should_skip_folder(folder_name: str) -> bool:
    """Check if folder should be skipped based on naming rules"""
    lower_name = folder_name.lower()
    return any(lower_name.startswith(prefix) for prefix in SKIP_PREFIXES)


def _is_folder_empty(folder_path: str) -> bool:
    """Check if folder is empty or contains only hidden files"""
    try:
        items = os.listdir(folder_path)
        # Consider folder empty if it has no visible files/dirs
        visible_items = [item for item in items if not item.startswith('.')]
        return len(visible_items) == 0
    except (OSError, PermissionError):
        return True


def _has_docker_compose(folder_path: str) -> bool:
    """Check if folder contains docker-compose files"""
    try:
        items = os.listdir(folder_path)
        return any(
            item.startswith("docker-compose") and item.endswith((".yml", ".yaml"))
            for item in items
        )
    except (OSError, PermissionError):
        return False


def _parse_caddyfile_domains() -> Dict[str, str]:
    """
    Parse Caddyfile to extract domain mappings.
    Returns dict: {folder_name: domain}
    Best-effort only, may not catch all cases.
    """
    domains = {}
    if not os.path.exists(CADDYFILE_PATH):
        return domains

    try:
        with open(CADDYFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        # Simple pattern: look for domain.alshifalab.pk followed by reverse_proxy
        # This is a heuristic and may need refinement
        lines = content.split("\n")
        current_domain = None

        for line in lines:
            line = line.strip()
            # Match domain declarations like: lims.alshifalab.pk {
            domain_match = re.match(r"^([\w-]+\.alshifalab\.pk)\s*\{?", line)
            if domain_match:
                current_domain = domain_match.group(1)
                # Extract subdomain as potential app key
                subdomain = current_domain.split(".")[0]
                domains[subdomain] = current_domain

    except Exception:
        # Best-effort, ignore errors
        pass

    return domains


def _get_docker_containers() -> Dict[str, List[dict]]:
    """
    Get all Docker containers grouped by compose project.
    Returns dict: {project_name: [container_info, ...]}
    """
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)

        projects: Dict[str, List[dict]] = {}

        for container in containers:
            labels = container.labels or {}
            project = labels.get("com.docker.compose.project")
            service = labels.get("com.docker.compose.service")

            if project:
                if project not in projects:
                    projects[project] = []

                projects[project].append({
                    "name": container.name,
                    "image": container.image.tags[0] if container.image.tags else "",
                    "service": service,
                    "labels": labels,
                })

        return projects

    except Exception:
        return {}


def _derive_key_from_folder(folder_name: str) -> str:
    """Derive a safe key from folder name"""
    # Convert to lowercase, replace unsafe chars with hyphen
    key = folder_name.lower()
    key = re.sub(r"[^a-z0-9_-]+", "-", key)
    key = re.sub(r"-+", "-", key)  # Collapse multiple hyphens
    key = key.strip("-")
    return key


def _derive_name_from_key(key: str) -> str:
    """Derive a title-case name from key"""
    # Replace hyphens/underscores with spaces, title case
    name = key.replace("-", " ").replace("_", " ")
    return name.title()


def _identify_required_containers(containers: List[str], container_images: Dict[str, str]) -> List[str]:
    """
    Identify required containers (databases, critical services).
    Rules:
    - If any container has image containing "postgres" OR name contains "db" -> include those
    - Else include first container as required
    """
    required = []

    for container_name in containers:
        image = container_images.get(container_name, "").lower()
        name_lower = container_name.lower()

        if "postgres" in image or "db" in name_lower:
            required.append(container_name)

    if not required and containers:
        required = [containers[0]]

    return required


def scan_inventory(existing_manifest: Optional[Dict] = None) -> InventorySyncResult:
    """
    Scan server for applications and produce inventory sync result.

    Args:
        existing_manifest: Current manifest override (if any) to preserve settings

    Returns:
        InventorySyncResult with added/removed/updated apps and preview manifest
    """
    # Parse existing manifest
    existing_apps = {}
    if existing_manifest:
        for app in existing_manifest.get("apps", []):
            existing_apps[app["key"]] = app

    # Scan sources
    domain_map = _parse_caddyfile_domains()
    docker_projects = _get_docker_containers()

    # Scan folders
    scanned_apps: Dict[str, ScannedApp] = {}
    skipped_folders = []

    if os.path.exists(APPS_ROOT):
        for folder_name in os.listdir(APPS_ROOT):
            folder_path = os.path.join(APPS_ROOT, folder_name)

            if not os.path.isdir(folder_path):
                continue

            # Apply skip rules
            if _should_skip_folder(folder_name):
                skipped_folders.append(folder_name)
                continue

            if _is_folder_empty(folder_path):
                skipped_folders.append(folder_name)
                continue

            # Check if it's a candidate app
            has_compose = _has_docker_compose(folder_path)
            has_containers = folder_name in docker_projects

            if not has_compose and not has_containers:
                skipped_folders.append(folder_name)
                continue

            # It's a candidate app!
            key = _derive_key_from_folder(folder_name)
            name = _derive_name_from_key(key)

            # Get containers
            containers = []
            container_images = {}

            if has_containers:
                for cont_info in docker_projects[folder_name]:
                    containers.append(cont_info["name"])
                    container_images[cont_info["name"]] = cont_info["image"]

            # Determine domain
            domain = domain_map.get(folder_name) or domain_map.get(key)

            # Preserve existing backend_health_url and frontend_url if present
            existing = existing_apps.get(key, {})
            backend_health_url = existing.get("backend_health_url")
            frontend_url = existing.get("frontend_url")

            # Auto-generate frontend_url from domain if not present
            if not frontend_url and domain:
                frontend_url = f"https://{domain}"

            # Identify required containers
            required_containers = _identify_required_containers(containers, container_images)

            scanned_apps[key] = ScannedApp(
                key=key,
                name=existing.get("name", name),  # Preserve custom name if exists
                domain=domain,
                folder=folder_path,
                containers=containers,
                required_containers=required_containers,
                backend_health_url=backend_health_url,
                frontend_url=frontend_url,
            )

    # Determine changes
    existing_keys = set(existing_apps.keys())
    scanned_keys = set(scanned_apps.keys())

    added = []
    removed = []
    updated = []

    for key in scanned_keys:
        if key not in existing_keys:
            added.append(key)
        else:
            # Check if anything changed
            old = existing_apps[key]
            new = scanned_apps[key]

            if (
                old.get("containers") != new.containers
                or old.get("domain") != new.domain
                or old.get("folder") != new.folder
            ):
                updated.append(key)

    # Remove obsolete apps (folder missing AND no containers AND no domain)
    for key in existing_keys:
        if key not in scanned_keys:
            old = existing_apps[key]
            folder = old.get("folder", "")
            domain = old.get("domain")
            containers = old.get("containers", [])

            # Check if folder exists
            folder_exists = folder and os.path.exists(folder)

            # Check if containers exist
            containers_exist = False
            if containers:
                try:
                    client = docker.from_env()
                    for cont_name in containers:
                        try:
                            client.containers.get(cont_name)
                            containers_exist = True
                            break
                        except docker.errors.NotFound:
                            pass
                except Exception:
                    pass

            # Remove only if nothing exists
            if not folder_exists and not containers_exist and not domain:
                removed.append(key)
            else:
                # Keep the app even though it wasn't scanned
                scanned_apps[key] = ScannedApp(
                    key=key,
                    name=old.get("name", key),
                    domain=old.get("domain"),
                    folder=old.get("folder", ""),
                    containers=old.get("containers", []),
                    required_containers=old.get("required_containers", []),
                    backend_health_url=old.get("backend_health_url"),
                    frontend_url=old.get("frontend_url"),
                )

    # Build preview manifest
    preview_apps = []
    for key in sorted(scanned_apps.keys()):
        app = scanned_apps[key]
        preview_apps.append({
            "key": app.key,
            "name": app.name,
            "domain": app.domain,
            "folder": app.folder,
            "containers": app.containers,
            "required_containers": app.required_containers,
            "backend_health_url": app.backend_health_url,
            "frontend_url": app.frontend_url,
        })

    preview_manifest = {"apps": preview_apps}

    return InventorySyncResult(
        added=added,
        removed=removed,
        updated=updated,
        skipped_folders=skipped_folders,
        preview_manifest=preview_manifest,
    )


def write_manifest_override(manifest_data: Dict, override_path: str) -> None:
    """
    Write manifest override to disk atomically.

    Args:
        manifest_data: Manifest dict with 'apps' key
        override_path: Path to manifest.override.yml
    """
    os.makedirs(os.path.dirname(override_path), exist_ok=True)

    tmp_path = f"{override_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest_data, f, sort_keys=False, default_flow_style=False)

    os.replace(tmp_path, override_path)
