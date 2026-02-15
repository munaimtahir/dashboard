from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import APIError, DockerException, NotFound

from .models import ContainerInfo, DiscoverComposeProject, DiscoverContainer, DiscoverResponse


def docker_client():
    # Uses /var/run/docker.sock mounted into the container.
    return docker.from_env()


def docker_ping() -> bool:
    try:
        c = docker_client()
        c.ping()
        return True
    except Exception:
        return False


def get_container_info(names: List[str]) -> List[ContainerInfo]:
    c = docker_client()
    out: List[ContainerInfo] = []
    for name in names:
        try:
            cont = c.containers.get(name)
            state = cont.attrs.get("State", {})
            status = (state.get("Status") or cont.status or "unknown")
            running = bool(state.get("Running"))
            exit_code = state.get("ExitCode")
            started_at = state.get("StartedAt")
            finished_at = state.get("FinishedAt")
            out.append(
                ContainerInfo(
                    name=name,
                    exists=True,
                    status=str(status),
                    running=running,
                    exit_code=int(exit_code) if exit_code is not None else None,
                    started_at=str(started_at) if started_at else None,
                    finished_at=str(finished_at) if finished_at else None,
                )
            )
        except NotFound:
            out.append(
                ContainerInfo(
                    name=name,
                    exists=False,
                    status="missing",
                    running=False,
                    exit_code=None,
                    started_at=None,
                    finished_at=None,
                )
            )
        except Exception as e:
            out.append(
                ContainerInfo(
                    name=name,
                    exists=False,
                    status=f"error: {e}",
                    running=False,
                    exit_code=None,
                    started_at=None,
                    finished_at=None,
                )
            )
    return out


def tail_logs(container_name: str, lines: int) -> str:
    c = docker_client()
    cont = c.containers.get(container_name)
    raw = cont.logs(tail=lines)
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return str(raw)


def action_on_containers(action: str, container_names: List[str]) -> Tuple[bool, Dict[str, str], Optional[str]]:
    c = docker_client()
    per: Dict[str, str] = {}
    ok = True
    err: Optional[str] = None

    for name in container_names:
        try:
            cont = c.containers.get(name)
            if action == "start":
                cont.start()
            elif action == "stop":
                cont.stop(timeout=10)
            elif action == "restart":
                cont.restart(timeout=10)
            else:
                raise ValueError("unknown action")
            per[name] = "ok"
        except NotFound:
            ok = False
            per[name] = "missing"
            err = err or f"container not found: {name}"
        except Exception as e:
            ok = False
            per[name] = f"error: {e}"
            err = err or str(e)

    return ok, per, err


def _minimal_state(attrs: Dict[str, Any]) -> Dict[str, Any]:
    state = dict(attrs.get("State") or {})
    keep = ("Status", "Running", "Restarting", "OOMKilled", "Dead", "Pid", "ExitCode", "Error", "StartedAt", "FinishedAt")
    return {k: state.get(k) for k in keep if k in state}


def _format_ports(attrs: Dict[str, Any]) -> List[str]:
    ports = (attrs.get("NetworkSettings") or {}).get("Ports") or {}
    out: List[str] = []
    for container_port, bindings in ports.items():
        if not bindings:
            out.append(str(container_port))
            continue
        for b in bindings:
            host_ip = (b or {}).get("HostIp") or ""
            host_port = (b or {}).get("HostPort") or ""
            if host_ip and host_port:
                out.append(f"{host_ip}:{host_port}->{container_port}")
            elif host_port:
                out.append(f"{host_port}->{container_port}")
            else:
                out.append(str(container_port))
    return out


def list_container_names(limit: int = 2000) -> set[str]:
    c = docker_client()
    names: set[str] = set()
    for cont in c.containers.list(all=True)[:limit]:
        try:
            attrs = cont.attrs
            name = (attrs.get("Name") or "").lstrip("/") or cont.name
            if name:
                names.add(name)
        except Exception:
            continue
    return names


def discover_inventory(
    *,
    limit: int = 2000,
    project: Optional[str] = None,
    contains: Optional[str] = None,
) -> DiscoverResponse:
    c = docker_client()
    containers: List[DiscoverContainer] = []
    q = (contains or "").strip().lower()
    for cont in c.containers.list(all=True)[:limit]:
        try:
            attrs = cont.attrs
            labels = dict((attrs.get("Config") or {}).get("Labels") or {})
            name = (attrs.get("Name") or "").lstrip("/") or cont.name
            compose_project = labels.get("com.docker.compose.project")
            compose_service = labels.get("com.docker.compose.service")
            image = str(cont.image.tags[0] if cont.image.tags else cont.image.short_id)

            if project and compose_project != project:
                continue

            if q:
                hay = " ".join(
                    [
                        name or "",
                        image or "",
                        compose_project or "",
                        compose_service or "",
                    ]
                ).lower()
                if q not in hay:
                    continue

            containers.append(
                DiscoverContainer(
                    id=str(cont.id)[:12],
                    name=str(name),
                    image=str(image),
                    status=str((attrs.get("State") or {}).get("Status") or cont.status or "unknown"),
                    state=_minimal_state(attrs),
                    created=str(attrs.get("Created") or ""),
                    ports=_format_ports(attrs),
                    compose_project=str(compose_project) if compose_project else None,
                    compose_service=str(compose_service) if compose_service else None,
                    labels=labels,
                )
            )
        except Exception:
            continue

    containers.sort(
        key=lambda x: (
            (x.compose_project or "zzz"),
            (x.compose_service or "zzz"),
            x.name,
        )
    )

    projects: Dict[str, Dict[str, Any]] = {}
    for c0 in containers:
        proj = c0.compose_project or "unknown"
        d = projects.setdefault(proj, {"services": set(), "containers": []})
        if c0.compose_service:
            d["services"].add(c0.compose_service)
        d["containers"].append(c0.name)

    compose_projects = [
        DiscoverComposeProject(
            project=p,
            services=sorted(list(d["services"])),
            containers=d["containers"],
        )
        for p, d in sorted(projects.items(), key=lambda kv: kv[0])
    ]

    return DiscoverResponse(containers=containers, compose_projects=compose_projects)
