from uuid import UUID

from pydantic import BaseModel, Field


class EnsureProjectNetworkInput(BaseModel):
    project_id: UUID
    name: str = Field(default="Project Network", max_length=255)


class GetLegacyProjectNetworkInput(BaseModel):
    project_id: UUID
