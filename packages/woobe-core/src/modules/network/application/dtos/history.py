from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ListNetworkSessionsInput(BaseModel):
    project_id: UUID
    network_id: UUID


class ListNetworkSessionMessagesInput(BaseModel):
    project_id: UUID
    network_id: UUID
    network_session_id: UUID
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=200, ge=1, le=500)


class ResetNetworkSessionContextInput(BaseModel):
    project_id: UUID
    network_id: UUID
    network_session_id: UUID


class ListNetworkExecutionEventsInput(BaseModel):
    project_id: UUID
    execution_id: UUID
    after_sequence: int = Field(default=0, ge=0)
    limit: int = Field(default=500, ge=1, le=500)


class NetworkSessionHistoryOutput(BaseModel):
    id: UUID
    network_version_id: UUID | None = None
    environment: str
    title: str
    status: str
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    message_count: int
    trace_count: int


class NetworkExecutionEventOutput(BaseModel):
    id: UUID
    sequence: int
    event_type: str
    invocation_id: UUID | None = None
    parent_invocation_id: UUID | None = None
    node_id: UUID | None = None
    agent_id: UUID | None = None
    depth: int | None = None
    payload: dict[str, Any]
    created_at: datetime | None = None


class NetworkExecutionHistoryOutput(BaseModel):
    id: UUID
    status: str
    draft_revision: int | None = None
    network_version_id: UUID | None = None
    root_trace_id: UUID | None = None
    failure_code: str | None = None
    failure: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    events: list[NetworkExecutionEventOutput]


class NetworkMessageHistoryOutput(BaseModel):
    id: UUID
    network_execution_id: UUID | None = None
    role: str
    content: str
    data: dict[str, Any] | None = None
    created_at: datetime | None = None
    execution: NetworkExecutionHistoryOutput | None = None
