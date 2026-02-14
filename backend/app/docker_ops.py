from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import docker
from docker.errors import APIError, DockerException, NotFound

from .models import ContainerInfo, DiscoverContainer


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
            out.append(
                ContainerInfo(
                    name=name,
                    exists=True,
                    status=str(status),
                    running=running,
                    exit_code=int(exit_code) if exit_code is not None else None,
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


def discover_containers(limit: int = 250) -> List[DiscoverContainer]:
    c = docker_client()
    out: List[DiscoverContainer] = []
    for cont in c.containers.list(all=True)[:limit]:
        try:
            attrs = cont.attrs
            out.append(
                DiscoverContainer(
                    id=cont.id,
                    name=(attrs.get("Name") or "").lstrip("/") or cont.name,
                    image=str(cont.image.tags[0] if cont.image.tags else cont.image.short_id),
                    status=str(attrs.get("State", {}).get("Status") or cont.status or "unknown"),
                    state=str(attrs.get("State", {}).get("Status") or cont.status or "unknown"),
                    labels=dict(attrs.get("Config", {}).get("Labels") or {}),
                )
            )
        except Exception:
            continue
    return out
