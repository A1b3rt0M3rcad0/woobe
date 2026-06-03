from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType


@dataclass
class DocumentCollection:
    project_id: UUID | None = None
    name: str = ""
    description: str | None = None
    status: CollectionStatus = CollectionStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AgentCollection:
    agent_id: UUID
    collection_id: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Document:
    project_id: UUID | None = None
    collection_id: UUID | None = None
    title: str = ""
    file_name: str = ""
    content_type: str = ""
    size_bytes: int = 0
    storage_key: str = ""
    parser: ParserType = ParserType.TEXT
    status: DocumentStatus = DocumentStatus.UPLOADED
    error: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    sha256: str | None = None
    indexed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class DocumentChunk:
    project_id: UUID | None = None
    collection_id: UUID | None = None
    document_id: UUID | None = None
    content: str = ""
    chunk_index: int = 0
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    data: dict | None = None
    embedding: list[float] | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None
