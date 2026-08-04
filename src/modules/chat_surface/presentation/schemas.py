from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


DEFAULT_CHAT_SURFACE_APPEARANCE: dict[str, Any] = {
    "theme": "system",
    "primary_color": "#5B47E0",
    "title": "Woobe",
    "placeholder": "Type a message…",
    "welcome_message": None,
}

_APPEARANCE_KEYS = frozenset(DEFAULT_CHAT_SURFACE_APPEARANCE)
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_appearance_config(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    unsupported = sorted(set(raw) - _APPEARANCE_KEYS)
    if unsupported:
        raise ValueError(
            f"Unsupported ChatSurface appearance fields: {', '.join(unsupported)}"
        )

    normalized = dict(DEFAULT_CHAT_SURFACE_APPEARANCE)
    normalized.update(raw)

    theme = normalized.get("theme")
    if theme not in {"light", "dark", "system"}:
        raise ValueError("appearance_config.theme must be light, dark or system")

    primary_color = normalized.get("primary_color")
    if not isinstance(primary_color, str) or not _HEX_COLOR.fullmatch(primary_color):
        raise ValueError("appearance_config.primary_color must be a #RRGGBB color")
    normalized["primary_color"] = primary_color.upper()

    for key, maximum in (("title", 80), ("placeholder", 120)):
        item = normalized.get(key)
        if not isinstance(item, str):
            raise ValueError(f"appearance_config.{key} must be a string")
        item = " ".join(item.split())
        if not item or len(item) > maximum:
            raise ValueError(
                f"appearance_config.{key} must contain between 1 and {maximum} characters"
            )
        normalized[key] = item

    welcome = normalized.get("welcome_message")
    if welcome is not None:
        if not isinstance(welcome, str):
            raise ValueError("appearance_config.welcome_message must be a string")
        welcome = welcome.strip()
        if len(welcome) > 500:
            raise ValueError(
                "appearance_config.welcome_message must contain at most 500 characters"
            )
        normalized["welcome_message"] = welcome or None

    return normalized


class CreateChatSurfaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_type: str
    target_id: UUID
    allowed_origins: list[str] = Field(default_factory=list, max_length=32)
    appearance_config: dict[str, Any] = Field(
        default_factory=lambda: dict(DEFAULT_CHAT_SURFACE_APPEARANCE)
    )
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

    @field_validator("appearance_config")
    @classmethod
    def validate_appearance_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_appearance_config(value)


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

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("ChatSurface name cannot be blank")
        return normalized

    @field_validator("appearance_config")
    @classmethod
    def validate_optional_appearance(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return normalize_appearance_config(value) if value is not None else None


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
