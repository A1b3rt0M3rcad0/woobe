from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from modules.core.domain.enums import (
    ApiKeyStatus,
    RuntimeEnvironment,
    RuntimeInterface,
)


class CreateRuntimeApiKeyInput(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    agent_id: UUID
    environment: RuntimeEnvironment
    interfaces: list[RuntimeInterface] = Field(min_length=1, max_length=3)
    created_by_user_id: UUID
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Runtime key name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("interfaces")
    @classmethod
    def normalize_interfaces(
        cls, value: list[RuntimeInterface]
    ) -> list[RuntimeInterface]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_expiration(self) -> "CreateRuntimeApiKeyInput":
        if self.expires_at is None:
            return self
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ValueError("Runtime key expiration must be in the future")
        self.expires_at = expires_at
        return self


class CreateRuntimeApiKeyOutput(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    key: str
    key_prefix: str
    scopes: list[str]
    kind: str
    agent_id: UUID
    environment: RuntimeEnvironment
    interfaces: list[str]
    status: ApiKeyStatus
    expires_at: datetime | None = None
    created_at: datetime | None = None
