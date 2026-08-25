from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.core.domain.enums import ProjectStatus


class GetProjectInput(BaseModel):
    project_id: UUID


class GetProjectOutput(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
