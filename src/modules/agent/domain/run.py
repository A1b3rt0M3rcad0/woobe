from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

import uuid6


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


@dataclass
class AgentRun:
    """One logical execution of one Agent."""

    project_id: UUID
    agent_id: UUID
    trace_id: UUID
    environment: str
    origin: str
    input_message: str
    execution_snapshot: dict[str, Any]
    id: UUID = field(default_factory=uuid6.uuid7)
    session_id: UUID | None = None
    agent_release_id: UUID | None = None
    input_message_id: UUID | None = None
    output_message_id: UUID | None = None
    network_execution_id: UUID | None = None
    network_invocation_id: UUID | None = None
    parent_run_id: UUID | None = None
    rerun_of_run_id: UUID | None = None
    status: AgentRunStatus = AgentRunStatus.RUNNING
    usage: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
