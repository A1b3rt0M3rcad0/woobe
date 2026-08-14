from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    workspace_id: UUID
    name: str
    slug: str


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    slug: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    scopes: list[str] = Field(min_length=1, max_length=16)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID | None = None
    name: str
    description: str | None = None
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    kind: str = "project"
    agent_id: UUID | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    environment: str | None = None
    interfaces: list[str] = Field(default_factory=list)
    status: str
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    rotated_from_id: UUID | None = None
    created_at: datetime | None = None


class CreatedApiKeyResponse(ApiKeyResponse):
    key: str


class ApiKeyCredentialResponse(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    kind: str
    agent_id: UUID | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    environment: str | None = None
    updated_at: datetime | None = None
