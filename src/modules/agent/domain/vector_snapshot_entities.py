from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

VECTOR_SNAPSHOT_BUILDING = "BUILDING"
VECTOR_SNAPSHOT_READY = "READY"
VECTOR_SNAPSHOT_FAILED = "FAILED"
VECTOR_SNAPSHOT_ARCHIVED = "ARCHIVED"
VECTOR_SNAPSHOT_DELETED = "DELETED"

VECTOR_SNAPSHOT_STAGE_QUEUED = "QUEUED"
VECTOR_SNAPSHOT_STAGE_PARSING = "PARSING"
VECTOR_SNAPSHOT_STAGE_CHUNKING = "CHUNKING"
VECTOR_SNAPSHOT_STAGE_EMBEDDING = "EMBEDDING"
VECTOR_SNAPSHOT_STAGE_WRITING = "WRITING"
VECTOR_SNAPSHOT_STAGE_READY = "READY"
VECTOR_SNAPSHOT_STAGE_FAILED = "FAILED"


@dataclass
class VectorSnapshot:
    project_id: UUID
    collection_id: UUID
    version: str
    embedding_provider_model_id: UUID
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int = 1536
    status: str = VECTOR_SNAPSHOT_BUILDING
    build_stage: str = VECTOR_SNAPSHOT_STAGE_QUEUED
    description: str | None = None
    chunk_size: int = 800
    chunk_overlap: int = 120
    chunking_strategy: str = "recursive_text"
    parser_config: dict[str, Any] | None = None
    build_config: dict[str, Any] | None = None
    snapshot_hash: str | None = None
    build_config_hash: str | None = None
    document_count: int = 0
    chunk_count: int = 0
    vector_count: int = 0
    total_document_count: int = 0
    processed_document_count: int = 0
    total_chunk_count: int = 0
    processed_chunk_count: int = 0
    embedded_chunk_count: int = 0
    current_document_id: UUID | None = None
    locked_at: datetime | None = None
    locked_by: str | None = None
    attempt_count: int = 0
    error_message: str | None = None
    created_by: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class VectorSnapshotDocument:
    vector_snapshot_id: UUID
    document_id: UUID
    document_sha256: str | None
    document_title: str
    file_name: str
    parser: str
    status_at_build: str
    chunk_count: int = 0
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class VectorSnapshotChunk:
    vector_snapshot_id: UUID
    project_id: UUID
    collection_id: UUID
    document_id: UUID
    content: str
    content_hash: str
    chunk_index: int
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    data: dict[str, Any] | None = None
    embedding: list[float] | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None
