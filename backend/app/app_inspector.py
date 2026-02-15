from __future__ import annotations

import os
import subprocess
import re
import time
from typing import Dict, List, Any, Optional, Set
from docker.client import DockerClient
from .manifest import ManifestApp

HOST_ROOT = os.getenv("HOST_ROOT", "/host")
# Prefer the proxy source Caddyfile
CADDYFILE_PATH = os.getenv("HOST_CADDYFILE", os.path.join(HOST_ROOT, "home/munaim/srv/proxy/caddy/Caddyfile"))

def _host_path(p: str) -> str:
    if not p:
        return ""
    if p.startswith(HOST_ROOT):
        return p
    return os.path.join(HOST_ROOT, p.lstrip("/"))

def _du_sm(path: str, timeout: int = 2) -> Optional[int]:
    """Execute du -sm on host path with timeout"""
    try:
        local_path = _host_path(path)
        if not os.path.exists(local_path):
            return None
        
        # Use subprocess with timeout
        r = subprocess.run(
            ["du", "-sm", "--", local_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode != 0:
            return None
        
        # Output is like: "123\t/path/to/dir"
        first = (r.stdout or "").strip().splitlines()[0].split()[0]
        return int(first)
    except (subprocess.TimeoutExpired, Exception):
        return None

def get_caddy_map() -> List[Dict[str, str]]:
    """
    Parses Caddyfile for domain -> upstream mappings.
    Returns list of {'domain': ..., 'upstream': ...}
    Best-effort regex parsing.
    """
    path = CADDYFILE_PATH
    if not os.path.exists(path):
        # Fallback to system-wide
        path = _host_path("/etc/caddy/Caddyfile")
        
    mappings = []
    if not os.path.exists(path):
        return mappings

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for domain blocks and reverse_proxy directives
        # Pattern: domain { ... reverse_proxy upstream ... }
        # This handles blocks with curly braces
        blocks = re.finditer(r'([a-zA-Z0-9\.\-]+)\s*\{([^}]*)\}', content, re.MULTILINE | re.DOTALL)
        for match in blocks:
            domain = match.group(1).strip()
            body = match.group(2)
            
            # Find reverse_proxy in the body
            proxy_match = re.search(r'reverse_proxy\s+([a-zA-Z0-9\.\-\:]+)', body)
            if proxy_match:
                mappings.append({
                    'domain': domain,
                    'upstream': proxy_match.group(1).strip()
                })
            
        # Also handle simple one-liners if any
        # domain reverse_proxy upstream
        # (Though Caddy usually prefers braces for proxies)
        
    except Exception:
        pass
    return mappings

def _detect_db_role(image: str, name: str) -> Optional[Dict[str, str]]:
    """Detect database type and role from image/name"""
    img_l = image.lower()
    name_l = name.lower()
    
    if "postgres" in img_l:
        return {"type": "PostgreSQL", "role": "database"}
    if "mysql" in img_l or "mariadb" in img_l:
        return {"type": "MySQL/MariaDB", "role": "database"}
    if "redis" in img_l:
        return {"type": "Redis", "role": "cache/db"}
    if "mongo" in img_l:
        return {"type": "MongoDB", "role": "database"}
    
    # Fallback to name if image is generic but name is indicative
    if "db" in name_l or "database" in name_l:
        return {"type": "unknown", "role": "database"}
        
    return None

def _get_listening_ports() -> List[int]:
    """Check what ports are listening on host via ss -ltnp"""
    try:
        # We need to run this via host-level access if possible, or just skip if restricted.
        # But for this dashboard, we usually have enough perms or host-gateway.
        # However, ss -ltnp might need sudo. Let's try it without first.
        r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=2)
        ports = []
        for line in r.stdout.splitlines():
            # Look for *:PORT or 0.0.0.0:PORT
            match = re.search(r'[:](\d+)\s+', line)
            if match:
                ports.append(int(match.group(1)))
        return sorted(list(set(ports)))
    except Exception:
        return []

def inspect_app(app_key: str, manifest_app: ManifestApp, docker_client: DockerClient, caddy_map: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Main inspector function.
    Collects all 'reality' data for an app.
    """
    issues = []
    
    # A) App Identity
    folder = manifest_app.folder
    local_folder = _host_path(folder)
    folder_exists = os.path.isdir(local_folder)
    
    # B) Containers
    containers_data = []
    compose_project = None
    compose_services: Set[str] = set()
    
    app_containers_names = set(manifest_app.containers)
    
    # Find containers by name OR by labels (if project matches folder name)
    # But manifest is the source of truth for 'owned' containers in this dashboard.
    try:
        all_containers = docker_client.containers.list(all=True)
    except Exception as e:
        return {"error": f"Docker API error: {e}", "issues": [str(e)]}

    # Map for easy lookup
    app_containers = [c for c in all_containers if c.name in app_containers_names]
    
    # Also look for containers that might belong but aren't in manifest (optional discovery)
    # But the prompt says "For each container belonging to the app"
    # and mentions "compose_project (from container labels)".
    
    # If no containers found by name, try finding by label com.docker.compose.project == app_key
    if not app_containers:
        app_containers = [c for c in all_containers if c.labels.get('com.docker.compose.project') == app_key]
        if app_containers:
            # Update inferred names for data collection
            for c in app_containers:
                app_containers_names.add(c.name)

    if not app_containers and app_containers_names:
        issues.append("No active or stopped containers found for this app")

    mounts_all = []
    
    for c in app_containers:
        attrs = c.attrs
        labels = attrs.get('Config', {}).get('Labels', {})
        proj = labels.get('com.docker.compose.project')
        svc = labels.get('com.docker.compose.service')
        
        if proj: compose_project = proj
        if svc: compose_services.add(svc)
        
        # Env summary (redacted)
        env_keys = [e.split('=')[0] for e in attrs.get('Config', {}).get('Env', [])]
        
        # Networks
        nets = []
        settings = attrs.get('NetworkSettings', {})
        for net_name, net_data in settings.get('Networks', {}).items():
            nets.append({
                'name': net_name,
                'ip_address': net_data.get('IPAddress'),
                'aliases': net_data.get('Aliases')
            })

        # Ports
        ports = []
        p_map = settings.get('Ports', {}) or {}
        for c_port, host_bindings in p_map.items():
            if host_bindings:
                for b in host_bindings:
                    host_ip = b.get('HostIp', '0.0.0.0')
                    host_port = b.get('HostPort')
                    ports.append(f"{host_ip}:{host_port}->{c_port}")
            else:
                ports.append(f"{c_port}")

        # Image info
        image_name = ""
        try:
            image_name = c.image.tags[0] if c.image.tags else c.image.short_id
        except:
            image_name = attrs.get('Config', {}).get('Image', 'unknown')

        state = attrs.get('State', {})
        c_info = {
            'name': c.name,
            'id_short': c.id[:12],
            'image': image_name,
            'created': attrs.get('Created'),
            'status': state.get('Status'),
            'health': state.get('Health', {}).get('Status', 'none'),
            'restart_count': attrs.get('RestartCount', 0),
            'exit_code': state.get('ExitCode'),
            'labels': labels,
            'ports': ports,
            'networks': nets,
            'env_keys': env_keys
        }
        
        # DB detection
        db_class = _detect_db_role(image_name, c.name)
        if db_class:
            c_info['db_role'] = db_class
            
        containers_data.append(c_info)
        
        # Mounts
        for m in attrs.get('Mounts', []):
            mounts_all.append({
                'container': c.name,
                'type': m.get('Type'),
                'source': m.get('Source'),
                'destination': m.get('Destination'),
                'rw': m.get('RW')
            })

    # C) Storage grouping
    named_volumes = {}
    bind_mounts = {}
    
    for m in mounts_all:
        usage = {
            'container': m['container'],
            'destination': m['destination'],
            'rw': m['rw']
        }
        if m['type'] == 'volume':
            v_name = m['source']
            if v_name not in named_volumes:
                named_volumes[v_name] = []
            named_volumes[v_name].append(usage)
        elif m['type'] == 'bind':
            src = m['source']
            if src not in bind_mounts:
                bind_mounts[src] = []
            bind_mounts[src].append(usage)
            
            # Awareness flag for mounts outside standard root
            if not src.startswith('/home/munaim/srv/'):
                issues.append(f"Bind mount points outside /home/munaim/srv: {src}")

    # D) Volume metadata (best effort)
    volume_details = []
    for v_name, usages in named_volumes.items():
        try:
            vol = docker_client.volumes.get(v_name)
            v_attrs = vol.attrs
            mt = v_attrs.get('Mountpoint')
            size_mb = _du_sm(mt) if mt else None
            
            volume_details.append({
                'name': v_name,
                'driver': v_attrs.get('Driver'),
                'mountpoint': mt,
                'size_estimate_mb': size_mb,
                'used_by': usages,
                'warning': "size unknown or permission denied" if size_mb is None else None
            })
        except Exception:
            volume_details.append({'name': v_name, 'error': 'volume metadata inaccessible', 'used_by': usages})

    # E) Folder sizing
    folder_size = _du_sm(folder) if folder_exists else None
    media_path = os.path.join(folder, "media") if folder else None
    uploads_path = os.path.join(folder, "uploads") if folder else None
    
    media_size = _du_sm(media_path) if media_path and os.path.isdir(_host_path(media_path)) else None
    uploads_size = _du_sm(uploads_path) if uploads_path and os.path.isdir(_host_path(uploads_path)) else None
    
    if folder_exists and folder_size is None:
        issues.append(f"Folder size estimation timed out for {folder}")

    # F) Database detection summary
    databases = []
    for c in containers_data:
        if 'db_role' in c:
            databases.append({
                'container': c['name'],
                'type': c['db_role']['type'],
                'role': c['db_role']['role'],
                'image': c['image'],
                'ports': c['ports']
            })

    # G) Routing / Caddy
    app_domain = manifest_app.domain
    routing_info = []
    domain_in_caddy = False
    
    if app_domain:
        # Check for direct match or subdomain match
        for m in caddy_map:
            if m['domain'] == app_domain:
                routing_info.append(m)
                domain_in_caddy = True
            elif m['domain'].startswith(f"{app_key}."):
                routing_info.append(m)
                domain_in_caddy = True

    if app_domain and not domain_in_caddy:
        issues.append(f"Expected domain {app_domain} not found in Caddy routing map")

    # Upstream listening check
    listening_ports = _get_listening_ports()
    for r in routing_info:
        upstream = r['upstream']
        if ':' in upstream:
            try:
                port = int(upstream.split(':')[-1])
                r['upstream_listening'] = port in listening_ports
            except:
                r['upstream_listening'] = None

    # H) Summary issues
    if not folder_exists:
        issues.append(f"Application folder does not exist on host: {folder}")
    
    unknown_size_vols = [v['name'] for v in volume_details if v.get('warning')]
    if unknown_size_vols:
        # Not a critical issue, just a info/warning
        pass

    return {
        'identity': {
            'key': app_key,
            'name': manifest_app.name,
            'domain': app_domain,
            'folder': folder,
            'folder_exists': folder_exists,
            'compose_project': compose_project,
            'compose_services': sorted(list(compose_services))
        },
        'containers': containers_data,
        'storage': {
            'folder_size_mb': folder_size,
            'media_size_mb': media_size,
            'uploads_size_mb': uploads_size,
            'named_volumes': volume_details,
            'bind_mounts': [
                {'source': src, 'usages': usages, 'size_mb': _du_sm(src)} 
                for src, usages in bind_mounts.items()
            ]
        },
        'databases': databases,
        'routing': routing_info,
        'issues': issues,
        'timestamp': time.time()
    }
