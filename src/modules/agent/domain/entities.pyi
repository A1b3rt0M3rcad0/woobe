from datetime import datetime
from typing import Any
from uuid import UUID


def __getattr__(name: str) -> Any: ...


class DocumentCollection:
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: Any
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Document:
    id: UUID
    project_id: UUID
    collection_id: UUID
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    parser: Any
    status: Any
    error: str | None
    page_count: int | None
    chunk_count: int | None
    indexed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class KnowledgeVersion:
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    collection_ids: list[UUID]
    document_ids: list[UUID] | None
    snapshot_metadata: dict[str, Any] | None
    status: Any
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Tool:
    id: UUID
    project_id: UUID
    agent_id: UUID | None
    name: str
    description: str | None
    type: Any
    config: dict[str, Any] | None
    input_schema: dict[str, Any] | None
    output_schema: dict[str, Any] | None
    risk_level: Any
    timeout_ms: int | None
    status: Any
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Secret:
    id: UUID
    project_id: UUID
    name: str
    type: Any
    encrypted_value: str
    data: dict[str, Any] | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Session:
    id: UUID
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None
    tenant_id: str | None
    user_id: str | None
    status: Any
    mode: Any
    data: dict[str, Any] | None
    last_message_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Message:
    id: UUID
    project_id: UUID
    agent_id: UUID
    session_id: UUID
    role: Any
    content: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    data: dict[str, Any] | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class AskJob:
    id: UUID
    project_id: UUID
    agent_id: UUID
    session_id: UUID
    status: str
    params: dict[str, Any] | None
    result: dict[str, Any] | None
    error: str | None
    trace_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...
