from __future__ import annotations

from typing import Optional, Tuple

from .docker_ops import tail_logs
from .models import ContainerInfo, UrlCheck


def _safe_tail(container: str, lines: int = 50, limit_chars: int = 2000) -> Optional[str]:
    try:
        txt = tail_logs(container, lines)
        txt = (txt or "").strip()
        if not txt:
            return None
        if len(txt) > limit_chars:
            return txt[-limit_chars:]
        return txt
    except Exception:
        return None


def evaluate(
    *,
    containers: list[str],
    container_info: list[ContainerInfo],
    backend_check: UrlCheck | None,
    frontend_check: UrlCheck | None,
) -> Tuple[str, str, str, str, dict, Optional[str]]:
    """
    Returns: (overall_status, failure_category, reason, recommendation, evidence, last_log_snippet)
    """
    evidence: dict = {}
    last_log_snippet: Optional[str] = None

    # 1) Container missing / stopped dominates.
    for c in container_info:
        if not c.exists:
            return (
                "DOWN",
                "CONTAINER_MISSING",
                f"Container missing ({c.name})",
                "Fix container name/stack, then restart app",
                {"container": c.name},
                None,
            )

    for c in container_info:
        if not c.running:
            evidence = {
                "container": c.name,
                "exit_code": c.exit_code,
                "started_at": c.started_at,
                "finished_at": c.finished_at,
            }
            last_log_snippet = _safe_tail(c.name, lines=60, limit_chars=2000)
            if c.exit_code is not None:
                reason = f"Container stopped (exit {c.exit_code})"
            else:
                reason = "Container stopped"
            return (
                "DOWN",
                "CONTAINER_EXITED",
                reason,
                "Restart app and check container logs",
                evidence,
                last_log_snippet,
            )

    # 2) Health checks.
    if backend_check is not None and not backend_check.ok:
        target = next((n for n in containers if "backend" in n.lower()), containers[0] if containers else None)
        if target:
            last_log_snippet = _safe_tail(target, lines=40, limit_chars=2000)
            evidence = {"container": target, "started_at": next((c.started_at for c in container_info if c.name == target), None)}
        return (
            "DEGRADED",
            "BACKEND_UNHEALTHY",
            "Backend health failing",
            "Check backend logs/health endpoint",
            evidence,
            last_log_snippet,
        )

    if frontend_check is not None and not frontend_check.ok:
        return (
            "DEGRADED",
            "FRONTEND_UNREACHABLE",
            "Frontend unreachable",
            "Check frontend/Caddy routing",
            {},
            None,
        )

    return ("HEALTHY", "OK", "OK", "No action", {}, None)

