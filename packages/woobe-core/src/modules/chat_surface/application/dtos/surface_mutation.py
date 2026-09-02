from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UpdateChatSurfaceInput(BaseModel):
    surface_id: UUID
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    allowed_origins: list[str] | None = Field(default=None, max_length=32)
    appearance_config: dict[str, Any] | None = None
    requests_per_minute: int | None = Field(default=None, ge=1, le=10_000)
    max_concurrent_runs: int | None = Field(default=None, ge=1, le=100)
    session_token_ttl_seconds: int | None = Field(default=None, ge=60, le=3600)


class ChangeChatSurfaceStatusInput(BaseModel):
    surface_id: UUID


__all__ = [
    "ChangeChatSurfaceStatusInput",
    "UpdateChatSurfaceInput",
]
