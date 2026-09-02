from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class NetworkRunObservation(BaseModel):
    id: UUID
    network_id: UUID
    network_version_id: UUID | None = None
    network_session_id: UUID
    project_id: UUID
    environment: str
    status: str
    input_message: str
    output_message: str | None = None
    parsed_output: dict[str, Any] | None = None
    output_parse_error: str | None = None
    root_trace_id: UUID | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None
