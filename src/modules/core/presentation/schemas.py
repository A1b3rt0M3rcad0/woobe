from uuid import UUID

from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    organization_id: UUID
    name: str
    slug: str


class ProjectResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: str


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: list[str] = []


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    status: str
