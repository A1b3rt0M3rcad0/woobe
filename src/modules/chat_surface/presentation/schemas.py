from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateChatSurfaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_type: str
    target_id: UUID
    allowed_origins: list[str] = Field(default_factory=list, max_length=32)
    appearance_config: dict[str, Any] = Field(default_factory=dict)
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    max_concurrent_runs: int = Field(default=10, ge=1, le=100)
    session_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("ChatSurface name cannot be blank")
        return normalized

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"agent", "network"}:
            raise ValueError("target_type must be agent or network")
        return normalized


class UpdateChatSurfaceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    allowed_origins: list[str] | None = Field(default=None, max_length=32)
    appearance_config: dict[str, Any] | None = None
    requests_per_minute: int | None = Field(default=None, ge=1, le=10_000)
    max_concurrent_runs: int | None = Field(default=None, ge=1, le=100)
    session_token_ttl_seconds: int | None = Field(
        default=None,
        ge=60,
        le=3600,
    )


class CreateSurfaceAccessKeyRequest(BaseModel):
    name: str = Field(default="Default ChatSurface key", min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class CreateSurfaceSessionRequest(BaseModel):
    external_reference: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class IssueSessionTokenRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=2048)


class StreamChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32768)
    metadata: dict[str, Any] | None = None

