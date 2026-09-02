from uuid import UUID

from pydantic import BaseModel, Field


class SubmitPublicNetworkRunInput(BaseModel):
    project_id: UUID
    network_id: UUID
    environment: str
    message: str = Field(min_length=1, max_length=32768)
    session_id: UUID | None = None
    tenant_id: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
