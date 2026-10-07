from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.application.dtos.rag_config_dtos import (
    RAGBuildConfig,
    RAGChunkingConfig,
    RAGParserConfig,
    VectorBuildPreviewOutput,
)


class CreateVectorSnapshotInput(BaseModel):
    project_id: UUID
    collection_id: UUID
    version: str | None = Field(default=None, min_length=1, max_length=64)
    embedding_provider_model_id: UUID
    description: str | None = Field(default=None, max_length=1000)
    chunk_size: int = Field(default=800, ge=200, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    chunking_strategy: str = Field(default="recursive_text", min_length=1, max_length=64)
    parser_config: dict[str, Any] | None = None
    build_config: dict[str, Any] | None = None
    created_by: UUID | None = None
    document_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=10000)


class PreviewVectorSnapshotInput(BaseModel):
    project_id: UUID
    collection_id: UUID
    parser: RAGParserConfig = RAGParserConfig()
    chunking: RAGChunkingConfig = RAGChunkingConfig()


class VectorSnapshotOutput(BaseModel):
    id: UUID
    project_id: UUID
    collection_id: UUID
    version: str
    description: str | None = None
    status: str
    build_stage: str = "QUEUED"
    embedding_provider_model_id: UUID
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    chunk_size: int
    chunk_overlap: int
    chunking_strategy: str
    parser_config: dict[str, Any] | None = None
    build_config: dict[str, Any] | None = None
    snapshot_hash: str | None = None
    build_config_hash: str | None = None
    document_count: int
    chunk_count: int
    vector_count: int = 0
    total_document_count: int = 0
    processed_document_count: int = 0
    total_chunk_count: int = 0
    processed_chunk_count: int = 0
    embedded_chunk_count: int = 0
    current_document_id: UUID | None = None
    error_message: str | None = None
    created_by: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionOverviewDocumentsOutput(BaseModel):
    active: int = 0
    ready: int = 0
    failed: int = 0
    pending: int = 0
    deleted: int = 0
    total_size_bytes: int = 0


class CollectionOverviewProcessingOutput(BaseModel):
    has_running_job: bool = False
    stage: str | None = None
    processed_documents: int = 0
    total_documents: int = 0
    processed_chunks: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0


class CollectionOverviewTechnologyOutput(BaseModel):
    embedding_provider_model_id: UUID | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    chunking_strategy: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    vector_store: str = "pgvector"
    distance_metric: str = "cosine"


class CollectionOverviewOutput(BaseModel):
    collection_id: UUID
    project_id: UUID
    rag_status: str
    documents: CollectionOverviewDocumentsOutput
    latest_snapshot: VectorSnapshotOutput | None = None
    latest_ready_snapshot: VectorSnapshotOutput | None = None
    processing: CollectionOverviewProcessingOutput
    technology: CollectionOverviewTechnologyOutput
    warnings: list[str] = []


class ListVectorSnapshotsInput(BaseModel):
    project_id: UUID
    collection_id: UUID


class GetVectorSnapshotInput(BaseModel):
    snapshot_id: UUID
    project_id: UUID | None = None


class GetCollectionOverviewInput(BaseModel):
    project_id: UUID
    collection_id: UUID


class SearchVectorSnapshotChunksInput(BaseModel):
    vector_snapshot_id: UUID
    embedding: list[float]
    limit: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)


__all__ = [
    "CollectionOverviewDocumentsOutput",
    "CollectionOverviewOutput",
    "CollectionOverviewProcessingOutput",
    "CollectionOverviewTechnologyOutput",
    "CreateVectorSnapshotInput",
    "GetCollectionOverviewInput",
    "GetVectorSnapshotInput",
    "ListVectorSnapshotsInput",
    "PreviewVectorSnapshotInput",
    "RAGBuildConfig",
    "RAGChunkingConfig",
    "RAGParserConfig",
    "SearchVectorSnapshotChunksInput",
    "VectorBuildPreviewOutput",
    "VectorSnapshotOutput",
]
