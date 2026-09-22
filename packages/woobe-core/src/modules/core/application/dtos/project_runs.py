from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ProjectRunsQuery(BaseModel):
    project_id: UUID
    network_id: UUID | None = None
    limit: int = Field(default=100, ge=1, le=200)
