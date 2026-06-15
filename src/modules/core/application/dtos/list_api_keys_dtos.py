from uuid import UUID

from pydantic import BaseModel

from modules.core.domain.enums import ApiKeyStatus


class ListApiKeysInput(BaseModel):
    project_id: UUID


class ListApiKeysOutput(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    status: ApiKeyStatus
