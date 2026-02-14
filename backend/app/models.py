from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_in_seconds: int


class ServerSummary(BaseModel):
    uptime_seconds: float
    loadavg_1: float
    loadavg_5: float
    loadavg_15: float
    cpu_percent: float
    ram_total_bytes: int
    ram_used_bytes: int
    ram_used_percent: float
    disk_total_bytes: int
    disk_used_bytes: int
    disk_used_percent: float
    docker_ok: bool
    caddy_ok: bool
    notes: List[str] = Field(default_factory=list)


class ContainerInfo(BaseModel):
    name: str
    exists: bool
    status: str
    running: bool
    exit_code: Optional[int] = None


class UrlCheck(BaseModel):
    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


class AppStatus(BaseModel):
    key: str
    name: str
    domain: Optional[str] = None
    containers: List[str]
    container_info: List[ContainerInfo]
    backend_health_url: Optional[str] = None
    frontend_url: Optional[str] = None
    backend_check: Optional[UrlCheck] = None
    frontend_check: Optional[UrlCheck] = None
    overall_status: str
    reason: str
    recommendation: str


class DiscoverContainer(BaseModel):
    id: str
    name: str
    image: str
    status: str
    state: str
    labels: Dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    ok: bool
    app_key: str
    action: str
    per_container: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None
