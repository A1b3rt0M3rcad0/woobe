from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from modules.core.domain.enums import (
    PROJECT_API_KEY_SCOPES,
    ApiKeyKind,
    ApiKeyStatus,
    RuntimeEnvironment,
    RuntimeTargetType,
)


class RevokeApiKeyInput(BaseModel):
    project_id: UUID
    api_key_id: UUID
    revoked_by_user_id: UUID | None = None
    revoked_by_control_key_id: UUID | None = None

    @model_validator(mode="after")
    def validate_actor(self) -> "RevokeApiKeyInput":
        if (self.revoked_by_user_id is None) == (
            self.revoked_by_control_key_id is None
        ):
            raise ValueError("Exactly one API key actor must be supplied")
        return self


class RevokeApiKeyOutput(BaseModel):
    id: UUID
    project_id: UUID
    status: ApiKeyStatus
    revoked_at: datetime


class RotateApiKeyInput(BaseModel):
    project_id: UUID
    api_key_id: UUID
    rotated_by_user_id: UUID | None = None
    rotated_by_control_key_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    scopes: list[str] | None = Field(default=None, max_length=16)
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("API key name cannot be blank")
        return normalized

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(value))
        if not normalized:
            raise ValueError("Rotated API key requires at least one scope")
        unknown = set(normalized) - PROJECT_API_KEY_SCOPES
        if unknown:
            raise ValueError(
                f"Unsupported API key scopes: {', '.join(sorted(unknown))}"
            )
        return normalized

    @model_validator(mode="after")
    def validate_expiration(self) -> "RotateApiKeyInput":
        if (self.rotated_by_user_id is None) == (
            self.rotated_by_control_key_id is None
        ):
            raise ValueError("Exactly one API key actor must be supplied")
        if self.expires_at is None:
            return self
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ValueError("API key expiration must be in the future")
        self.expires_at = expires_at
        return self


class RotateApiKeyOutput(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    key: str
    key_prefix: str
    scopes: list[str]
    kind: ApiKeyKind = ApiKeyKind.project
    agent_id: UUID | None = None
    target_type: RuntimeTargetType | None = None
    target_id: UUID | None = None
    environment: RuntimeEnvironment | None = None
    interfaces: list[str] = Field(default_factory=list)
    status: ApiKeyStatus
    expires_at: datetime | None = None
    created_at: datetime | None = None
    rotated_from_id: UUID


class UpdateApiKeyCredentialInput(BaseModel):
    project_id: UUID
    api_key_id: UUID
    updated_by_user_id: UUID | None = None
    updated_by_control_key_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_actor(self) -> "UpdateApiKeyCredentialInput":
        if (self.updated_by_user_id is None) == (
            self.updated_by_control_key_id is None
        ):
            raise ValueError("Exactly one API key actor must be supplied")
        return self

    @field_validator("name")
    @classmethod
    def normalize_credential_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("API key name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_credential_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UpdateApiKeyCredentialOutput(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    kind: ApiKeyKind
    agent_id: UUID | None = None
    target_type: RuntimeTargetType | None = None
    target_id: UUID | None = None
    environment: RuntimeEnvironment | None = None
    updated_at: datetime | None = None
