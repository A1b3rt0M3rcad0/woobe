from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus


class AgentCollectionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    collection_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AttachCollectionRequest(BaseModel):
    agent_id: UUID
    collection_id: UUID


class CreateCollectionRequest(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CollectionResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: CollectionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UploadDocumentRequest(BaseModel):
    project_id: UUID
    collection_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=0)
    storage_key: str = Field(..., max_length=512)


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    collection_id: UUID
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    status: DocumentStatus
    page_count: int | None = None
    chunk_count: int | None = None
    error: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SearchRequest(BaseModel):
    query: str
    collection_id: UUID
    limit: int = Field(default=10, ge=1, le=100)


class ChunkResponse(BaseModel):
    id: UUID
    content: str
    chunk_index: int
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    data: dict | None = None
    score: float | None = None
