from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AcceptNetworkExecutionInput(BaseModel):
    project_id: UUID
    network_id: UUID
    network_session_id: UUID
    message: str = Field(min_length=1, max_length=32768)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    expected_draft_revision: int | None = Field(default=None, ge=0)


class NetworkSessionAcceptanceState(BaseModel):
    id: UUID
    network_id: UUID
    network_version_id: UUID | None = None
    project_id: UUID
    environment: str
    status: str
    origin: str
    chat_surface_id: UUID | None = None


class NetworkVersionAcceptanceState(BaseModel):
    id: UUID
    network_id: UUID
    project_id: UUID
    version: str
    definition: dict[str, Any]
    resolved_bindings: dict[str, Any]
    composition_hash: str


class PersistNetworkExecutionInput(BaseModel):
    project_id: UUID
    network_id: UUID
    network_session_id: UUID
    network_version_id: UUID | None = None
    message: str
    idempotency_key: str | None = None
    environment: str
    origin: str
    chat_surface_id: UUID | None = None
    draft_revision: int | None = None
    definition_snapshot: dict[str, Any] | None = None
    resolved_bindings_snapshot: dict[str, Any] | None = None
    accepted_version: str | None = None
    accepted_composition_hash: str
    root_node_id: UUID
    limits: dict[str, int]


class AcceptedNetworkExecution(BaseModel):
    id: UUID
    network_id: UUID
    network_session_id: UUID
    project_id: UUID
    status: str
    created_at: datetime | None = None
