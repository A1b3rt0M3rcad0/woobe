from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateChatSurfaceInput(BaseModel):
    project_id: UUID
    actor_id: UUID
    target_release_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_type: Literal["agent", "network"]
    target_id: UUID
    allowed_origins: list[str] = Field(default_factory=list, max_length=32)
    appearance_config: dict[str, Any] = Field(default_factory=dict)
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    max_concurrent_runs: int = Field(default=10, ge=1, le=100)
    session_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)


class UpdateChatSurfaceInput(BaseModel):
    surface_id: UUID
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    allowed_origins: list[str] | None = Field(default=None, max_length=32)
    appearance_config: dict[str, Any] | None = None
    requests_per_minute: int | None = Field(default=None, ge=1, le=10_000)
    max_concurrent_runs: int | None = Field(default=None, ge=1, le=100)
    session_token_ttl_seconds: int | None = Field(default=None, ge=60, le=3600)


class RefreshChatSurfaceReleaseInput(BaseModel):
    surface_id: UUID
    target_release_id: UUID


class ActivateChatSurfaceInput(BaseModel):
    surface_id: UUID
    expected_target_release_id: UUID


class ChangeChatSurfaceStatusInput(BaseModel):
    surface_id: UUID


__all__ = [
    "ActivateChatSurfaceInput",
    "ChangeChatSurfaceStatusInput",
    "CreateChatSurfaceInput",
    "RefreshChatSurfaceReleaseInput",
    "UpdateChatSurfaceInput",
]
