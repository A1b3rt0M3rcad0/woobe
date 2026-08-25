from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.core.domain.enums import ProjectStatus


class CreateProjectInput(BaseModel):
    workspace_id: UUID
    name: str
    slug: str


class CreateProjectOutput(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime | None = None
