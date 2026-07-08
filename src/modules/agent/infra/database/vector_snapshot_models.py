from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modules.agent.infra.database.models import DocumentModel
from shared.infra.database.base import BaseModel


class VectorSnapshotModel(BaseModel):
    __tablename__ = "vector_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "collection_id",
            "version",
            name="uq_vector_snapshots_project_collection_version",
        ),
        Index("ix_vector_snapshots_project_collection_status", "project_id", "collection_id", "status"),
        Index(
            "uq_vector_snapshots_building_per_collection",
            "collection_id",
            unique=True,
            postgresql_where=text("status = 'BUILDING'"),
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("agent.document_collections.id"))
    version: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="BUILDING")
    build_stage: Mapped[str] = mapped_column(String(32), default="QUEUED")
    embedding_provider_model_id: Mapped[UUID] = mapped_column(ForeignKey("agent.provider_models.id"))
    embedding_provider: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(255))
    embedding_dimensions: Mapped[int] = mapped_column(Integer, default=1536)
    chunk_size: Mapped[int] = mapped_column(Integer, default=800)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=120)
    chunking_strategy: Mapped[str] = mapped_column(String(64), default="recursive_text")
    parser_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    build_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    build_config_hash: Mapped[str | None] = mapped_column(String(64))
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    total_document_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_document_count: Mapped[int] = mapped_column(Integer, default=0)
    total_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedded_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    current_document_id: Mapped[UUID | None]
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VectorSnapshotDocumentModel(BaseModel):
    __tablename__ = "vector_snapshot_documents"
    __table_args__ = (
        UniqueConstraint(
            "vector_snapshot_id",
            "document_id",
            name="uq_vector_snapshot_documents_snapshot_document",
        ),
        Index("ix_vector_snapshot_documents_snapshot", "vector_snapshot_id"),
        {"schema": "agent"},
    )

    vector_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.vector_snapshots.id", ondelete="CASCADE")
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("agent.documents.id"))
    document_sha256: Mapped[str | None] = mapped_column(String(64))
    document_title: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    parser: Mapped[str] = mapped_column(String(64))
    status_at_build: Mapped[str] = mapped_column(String(32))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)


class VectorSnapshotChunkModel(BaseModel):
    __tablename__ = "vector_snapshot_chunks"
    __table_args__ = (
        Index("ix_vector_snapshot_chunks_snapshot", "vector_snapshot_id"),
        Index("ix_vector_snapshot_chunks_document", "vector_snapshot_id", "document_id"),
        Index(
            "ix_vector_snapshot_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": "agent"},
    )

    vector_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.vector_snapshots.id", ondelete="CASCADE")
    )
    project_id: Mapped[UUID]
    collection_id: Mapped[UUID]
    document_id: Mapped[UUID] = mapped_column(ForeignKey("agent.documents.id"))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    chunk_index: Mapped[int]
    token_count: Mapped[int | None]
    page_number: Mapped[int | None]
    section_title: Mapped[str | None] = mapped_column(String(255))
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


Index(
    "uq_documents_active_collection_sha256",
    DocumentModel.__table__.c.collection_id,
    DocumentModel.__table__.c.sha256,
    unique=True,
    postgresql_where=text("status <> 'DELETED' AND sha256 IS NOT NULL"),
)
