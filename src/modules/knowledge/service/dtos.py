from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType


class CreateCollectionInput(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CreateCollectionOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: CollectionStatus
    created_at: datetime
    updated_at: datetime


class UploadDocumentInput(BaseModel):
    project_id: UUID
    collection_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=0)
    storage_key: str = Field(..., max_length=512)
    parser: ParserType = ParserType.TEXT


class UploadDocumentOutput(BaseModel):
    id: UUID
    project_id: UUID
    collection_id: UUID
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    parser: ParserType
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class DocumentChunkOutput(BaseModel):
    id: UUID
    content: str
    chunk_index: int
    token_count: int | None
    page_number: int | None
    section_title: str | None
    data: dict | None
    similarity: float | None = None


class SearchChunksInput(BaseModel):
    collection_id: UUID
    embedding: list[float]
    limit: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class SearchChunksOutput(BaseModel):
    results: list[DocumentChunkOutput]
    total: int

