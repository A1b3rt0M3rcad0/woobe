from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.core.domain.enums import ApiKeyStatus, ProjectStatus


class CreateProjectInput(BaseModel):
    organization_id: UUID
    name: str
    slug: str


class CreateProjectOutput(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime | None = None


class CreateApiKeyInput(BaseModel):
    project_id: UUID
    name: str
    scopes: list[str] = []
    created_by_user_id: UUID


class CreateApiKeyOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str
    key_hash: bytes
    status: ApiKeyStatus
    created_at: datetime


class ListProjectsInput(BaseModel):
    organization_id: UUID | None = None


class ListProjectsOutput(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GetProjectInput(BaseModel):
    project_id: UUID


class GetProjectOutput(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateProjectInput(BaseModel):
    project_id: UUID
    name: str | None = None
    slug: str | None = None


class UpdateProjectOutput(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListApiKeysInput(BaseModel):
    project_id: UUID


class ListApiKeysOutput(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    status: ApiKeyStatus
