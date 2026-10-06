from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from modules.core.domain.enums import (
    PROJECT_API_KEY_ACCEPTED_SCOPES,
    ApiKeyStatus,
)


class CreateApiKeyInput(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    scopes: list[str] = Field(min_length=1, max_length=16)
    created_by_user_id: UUID | None = None
    created_by_control_key_id: UUID | None = None
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("API key name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value))
        unknown = set(normalized) - PROJECT_API_KEY_ACCEPTED_SCOPES
        if unknown:
            raise ValueError(
                f"Unsupported API key scopes: {', '.join(sorted(unknown))}"
            )
        return normalized

    @model_validator(mode="after")
    def validate_expiration(self) -> "CreateApiKeyInput":
        if (self.created_by_user_id is None) == (
            self.created_by_control_key_id is None
        ):
            raise ValueError("Exactly one API key creator must be supplied")
        if self.expires_at is None:
            return self
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ValueError("API key expiration must be in the future")
        self.expires_at = expires_at
        return self


class CreateApiKeyOutput(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    key_prefix: str
    key_hash: bytes | None = None
    key: str = ""
    scopes: list[str] = Field(default_factory=list)
    status: ApiKeyStatus
    expires_at: datetime | None = None
    created_at: datetime | None = None
