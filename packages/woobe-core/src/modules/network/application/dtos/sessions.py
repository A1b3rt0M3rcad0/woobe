from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.network.domain.enums import NetworkEnvironment


class CreateNetworkSessionInput(BaseModel):
    project_id: UUID
    network_id: UUID
    environment: NetworkEnvironment
    title: str = Field(default="New Network session", max_length=255)
    tenant_id: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    external_session_id: str | None = Field(default=None, max_length=255)


class NetworkSessionOutput(BaseModel):
    id: UUID
    network_id: UUID
    network_version_id: UUID | None = None
    environment: str
    title: str
    status: str
    last_message_at: datetime | None = None
    message_count: int = 0
    trace_count: int = 0
    created_at: datetime | None = None
