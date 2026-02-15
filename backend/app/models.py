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
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


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
    failure_category: Optional[str] = None
    reason: str
    recommendation: str
    recommended_action: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    last_log_snippet: Optional[str] = None


class DiscoverContainer(BaseModel):
    id: str
    name: str
    image: str
    status: str
    state: Dict[str, Any] = Field(default_factory=dict)
    created: Optional[str] = None
    ports: List[str] = Field(default_factory=list)
    compose_project: Optional[str] = None
    compose_service: Optional[str] = None
    labels: Dict[str, Any] = Field(default_factory=dict)

class DiscoverComposeProject(BaseModel):
    project: str
    services: List[str] = Field(default_factory=list)
    containers: List[str] = Field(default_factory=list)


class DiscoverResponse(BaseModel):
    containers: List[DiscoverContainer] = Field(default_factory=list)
    compose_projects: List[DiscoverComposeProject] = Field(default_factory=list)


class ManifestAppEntry(BaseModel):
    key: str
    name: str
    domain: Optional[str] = None
    containers: List[str] = Field(default_factory=list)
    backend_health_url: Optional[str] = None
    frontend_url: Optional[str] = None


class ManifestResponse(BaseModel):
    apps: List[ManifestAppEntry] = Field(default_factory=list)


class ManifestUpsertRequest(BaseModel):
    key: str
    name: str
    domain: Optional[str] = None
    containers: List[str] = Field(default_factory=list)
    backend_health_url: Optional[str] = None
    frontend_url: Optional[str] = None
    allow_missing_containers: bool = False


class ActionResult(BaseModel):
    ok: bool
    app_key: str
    action: str
    per_container: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class ActionResponse(BaseModel):
    ok: bool
    app_key: str
    action: str
    per_container: Dict[str, str] = Field(default_factory=dict)
    exit_code: Optional[int] = None
    message: Optional[str] = None
    status: Optional[AppStatus] = None


class InventorySyncSummary(BaseModel):
    """Summary of inventory sync changes"""
    added: List[str] = Field(default_factory=list)
    removed: List[str] = Field(default_factory=list)
    updated: List[str] = Field(default_factory=list)
    skipped_folders: List[str] = Field(default_factory=list)


class InventoryPreviewResponse(BaseModel):
    """Response for inventory preview"""
    summary: InventorySyncSummary
    preview_manifest: Dict[str, Any]


class InventorySyncResponse(BaseModel):
    """Response for inventory sync"""
    summary: InventorySyncSummary
    manifest: Dict[str, Any]


class OpsStatusResponse(BaseModel):
    """Response for ops status check"""
    configured: bool
    reason: Optional[str] = None
    available_actions: List[str] = Field(default_factory=list)
    running_action: Optional[str] = None


class OpsActionResponse(BaseModel):
    """Response for ops action execution"""
    success: bool
    exit_code: int
    log_file: str
    tail: str
    message: str
    updated_app_status: Optional[AppStatus] = None
