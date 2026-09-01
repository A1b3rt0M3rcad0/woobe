from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None


class PublicCreateJobRequest(PublicRunRequest):
    pass
