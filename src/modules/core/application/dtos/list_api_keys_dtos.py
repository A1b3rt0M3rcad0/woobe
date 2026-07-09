from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.core.domain.enums import ApiKeyKind, ApiKeyStatus, RuntimeEnvironment


class ListApiKeysInput(BaseModel):
    project_id: UUID


class ListApiKeysOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    kind: ApiKeyKind = ApiKeyKind.project
    agent_id: UUID | None = None
    environment: RuntimeEnvironment | None = None
    interfaces: list[str] = Field(default_factory=list)
    status: ApiKeyStatus
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
