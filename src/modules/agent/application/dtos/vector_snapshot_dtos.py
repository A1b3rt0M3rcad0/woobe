from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateVectorSnapshotInput(BaseModel):
    project_id: UUID
    collection_id: UUID
    version: str = Field(..., min_length=1, max_length=64)
    embedding_provider_model_id: UUID
    description: str | None = Field(default=None, max_length=1000)
    chunk_size: int = Field(default=800, ge=200, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    chunking_strategy: str = Field(default="recursive_text", min_length=1, max_length=64)
    parser_config: dict[str, Any] | None = None
    created_by: UUID | None = None


class VectorSnapshotOutput(BaseModel):
    id: UUID
    project_id: UUID
    collection_id: UUID
    version: str
    description: str | None = None
    status: str
    embedding_provider_model_id: UUID
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    chunk_size: int
    chunk_overlap: int
    chunking_strategy: str
    parser_config: dict[str, Any] | None = None
    snapshot_hash: str | None = None
    document_count: int
    chunk_count: int
    error_message: str | None = None
    created_by: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListVectorSnapshotsInput(BaseModel):
    project_id: UUID
    collection_id: UUID


class GetVectorSnapshotInput(BaseModel):
    snapshot_id: UUID
    project_id: UUID | None = None


class SearchVectorSnapshotChunksInput(BaseModel):
    vector_snapshot_id: UUID
    embedding: list[float]
    limit: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
