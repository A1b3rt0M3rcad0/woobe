from typing import Any
from uuid import UUID

from pydantic import BaseModel


class UpdateChatSurfaceInput(BaseModel):
    surface_id: UUID
    name: str | None = None
    description: str | None = None
    allowed_origins: list[str] | None = None
    appearance_config: dict[str, Any] | None = None
    requests_per_minute: int | None = None
    max_concurrent_runs: int | None = None
    session_token_ttl_seconds: int | None = None


class ChangeChatSurfaceStatusInput(BaseModel):
    surface_id: UUID


__all__ = [
    "ChangeChatSurfaceStatusInput",
    "UpdateChatSurfaceInput",
]
