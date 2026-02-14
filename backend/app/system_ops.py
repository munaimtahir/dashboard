from __future__ import annotations

import os
import socket
import time
from typing import List, Tuple

import psutil

from .docker_ops import docker_ping


HOST_ROOT = os.getenv("HOST_ROOT", "/host")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "3"))


def _host_path(p: str) -> str:
    # p is an absolute host path like /proc/uptime
    return os.path.join(HOST_ROOT, p.lstrip("/"))


def read_uptime_seconds() -> float:
    try:
        with open(_host_path("/proc/uptime"), "r", encoding="utf-8") as f:
            return float(f.read().split()[0])
    except Exception:
        # Fallback to psutil (may be container-ish)
        return max(0.0, time.time() - psutil.boot_time())


def read_loadavg() -> Tuple[float, float, float]:
    try:
        with open(_host_path("/proc/loadavg"), "r", encoding="utf-8") as f:
            parts = f.read().split()
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return os.getloadavg()


def read_meminfo() -> Tuple[int, int, float]:
    # Returns (total_bytes, used_bytes, used_percent)
    try:
        mem = {}
        with open(_host_path("/proc/meminfo"), "r", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k.strip()] = v.strip()
        total_kb = int(mem["MemTotal"].split()[0])
        avail_kb = int(mem.get("MemAvailable", "0 kB").split()[0])
        used_kb = max(0, total_kb - avail_kb)
        used_percent = (used_kb / total_kb) * 100.0 if total_kb else 0.0
        return total_kb * 1024, used_kb * 1024, used_percent
    except Exception:
        vm = psutil.virtual_memory()
        return int(vm.total), int(vm.used), float(vm.percent)


def read_disk_usage() -> Tuple[int, int, float]:
    # Host root filesystem usage via /host
    try:
        usage = psutil.disk_usage(HOST_ROOT)
        return int(usage.total), int(usage.used), float(usage.percent)
    except Exception:
        usage = psutil.disk_usage("/")
        return int(usage.total), int(usage.used), float(usage.percent)


def read_cpu_percent() -> float:
    # Approx. cpu%. psutil uses current namespace but close enough for v1.
    try:
        return float(psutil.cpu_percent(interval=0.15))
    except Exception:
        return 0.0


def tcp_check(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def caddy_status() -> Tuple[bool, List[str]]:
    notes: List[str] = []

    # Try host gateway first (works on Linux with extra_hosts: host-gateway)
    host = "host.docker.internal"
    ok_80 = tcp_check(host, 80)
    ok_443 = tcp_check(host, 443)
    if ok_80 or ok_443:
        notes.append(f"Caddy TCP reachable via {host} (80={ok_80}, 443={ok_443})")
        return True, notes

    notes.append("Caddy TCP check failed (host gateway not reachable on 80/443)")
    return False, notes


def docker_status() -> Tuple[bool, List[str]]:
    ok = docker_ping()
    return ok, ["Docker ping ok" if ok else "Docker ping failed"]
