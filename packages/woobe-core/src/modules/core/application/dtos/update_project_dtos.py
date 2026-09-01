from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.core.domain.enums import ProjectStatus


class UpdateProjectInput(BaseModel):
    project_id: UUID
    name: str | None = None
    slug: str | None = None


class UpdateProjectOutput(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
