from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.domain.enums import CollectionStatus, DocumentStatus, KnowledgeVersionStatus, ParserType


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
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateCollectionInput(BaseModel):
    collection_id: UUID
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: CollectionStatus | None = None


class UpdateCollectionOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: CollectionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AttachCollectionInput(BaseModel):
    agent_id: UUID
    collection_id: UUID


class AttachCollectionOutput(BaseModel):
    id: UUID
    agent_id: UUID
    collection_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentCollectionOutput(BaseModel):
    id: UUID
    agent_id: UUID
    collection_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UploadDocumentInput(BaseModel):
    document_id: UUID | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    project_id: UUID
    collection_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=0)
    storage_key: str = Field(..., max_length=512)
    parser: ParserType = ParserType.TEXT


class UploadDocumentFileInput(BaseModel):
    project_id: UUID
    collection_id: UUID
    title: str | None = Field(default=None, max_length=255)


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
    page_count: int | None = None
    chunk_count: int | None = None
    error: str | None = None
    sha256: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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


class ListCollectionsInput(BaseModel):
    project_id: UUID | None = None


class GetCollectionInput(BaseModel):
    collection_id: UUID


class ListDocumentsInput(BaseModel):
    project_id: UUID | None = None
    collection_id: UUID | None = None


class GetDocumentInput(BaseModel):
    document_id: UUID


class CreateKnowledgeVersionInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str | None = Field(default=None, min_length=1, max_length=64)
    collection_ids: list[UUID] = []
    document_ids: list[UUID] | None = None
    snapshot_metadata: dict | None = None


class CreateKnowledgeVersionOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    collection_ids: list[UUID]
    document_ids: list[UUID] | None = None
    snapshot_metadata: dict | None = None
    status: KnowledgeVersionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListKnowledgeVersionsOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    collection_ids: list[UUID]
    document_ids: list[UUID] | None = None
    snapshot_metadata: dict | None = None
    status: KnowledgeVersionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
