from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ChatSurfaceState(BaseModel):
    id: UUID
    public_id: str
    project_id: UUID
    name: str
    description: str | None = None
    target_type: str
    target_id: UUID
    target_release_id: UUID
    environment: str
    status: str
    access_mode: str
    allowed_origins: list[str]
    appearance_config: dict[str, Any]
    requests_per_minute: int
    max_concurrent_runs: int
    session_token_ttl_seconds: int
    token_epoch: int
    activated_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ListChatSurfacesInput(BaseModel):
    project_id: UUID


class GetChatSurfaceInput(BaseModel):
    surface_id: UUID
