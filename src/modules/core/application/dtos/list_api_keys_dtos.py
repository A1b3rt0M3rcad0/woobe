from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.core.domain.enums import ApiKeyStatus


class ListApiKeysInput(BaseModel):
    project_id: UUID


class ListApiKeysOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    status: ApiKeyStatus
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
