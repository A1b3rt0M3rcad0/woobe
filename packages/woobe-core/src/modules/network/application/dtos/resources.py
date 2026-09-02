from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ListProjectNetworksInput(BaseModel):
    project_id: UUID


class CreateProjectNetworkInput(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)


class GetProjectNetworkInput(BaseModel):
    project_id: UUID
    network_id: UUID


class UpdateProjectNetworkInput(BaseModel):
    project_id: UUID
    network_id: UUID
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class NetworkResourceOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str
    draft_definition: dict[str, Any]
    draft_revision: int
    staging_version_id: UUID | None = None
    production_version_id: UUID | None = None
    agent_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
