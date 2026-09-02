from typing import Any
from uuid import UUID

from pydantic import BaseModel


class RerunNetworkExecutionInput(BaseModel):
    execution_id: UUID
    project_id: UUID
    idempotency_key: str | None = None


class NetworkRerunSource(BaseModel):
    id: UUID
    network_id: UUID
    network_version_id: UUID | None = None
    network_session_id: UUID
    project_id: UUID
    input_message: str
    draft_revision: int | None = None
    definition_snapshot: dict[str, Any] | None = None
    resolved_bindings_snapshot: dict[str, Any] | None = None
    status: str


class NetworkRerunSessionState(BaseModel):
    id: UUID
    status: str
    environment: str


class NetworkRerunExecutionState(BaseModel):
    id: UUID
    status: str


class RerunNetworkExecutionOutput(BaseModel):
    execution_id: UUID
    rerun_of_execution_id: UUID
    status: str
