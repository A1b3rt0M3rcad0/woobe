from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.domain.enums import CredentialStatus, Provider


class RotateProviderCredentialInput(BaseModel):
    secret: str = Field(min_length=1)
    rotated_by_user_id: UUID


class RotateProviderCredentialOutput(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    last_validated_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
