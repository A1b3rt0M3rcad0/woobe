from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    organization_id: UUID
    name: str
    slug: str


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    slug: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: list[str] = []


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    status: str
