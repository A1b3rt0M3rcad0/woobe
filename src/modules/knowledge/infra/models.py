from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class DocumentCollectionModel(BaseModel):
    __tablename__ = "document_collections"
    __table_args__ = {"schema": "knowledge"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")


class AgentCollectionModel(BaseModel):
    __tablename__ = "agent_collections"
    __table_args__ = (
        UniqueConstraint("agent_id", "collection_id"),
        {"schema": "knowledge"},
    )

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.document_collections.id")
    )


class DocumentModel(BaseModel):
    __tablename__ = "documents"
    __table_args__ = {"schema": "knowledge"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.document_collections.id")
    )
    title: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512))
    parser: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    sha256: Mapped[str | None] = mapped_column(String(64))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunkModel(BaseModel):
    __tablename__ = "document_chunks"
    __table_args__ = {"schema": "knowledge"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.document_collections.id")
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge.documents.id"))
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int]
    token_count: Mapped[int | None]
    page_number: Mapped[int | None]
    section_title: Mapped[str | None] = mapped_column(String(255))
    data: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


class KnowledgeVersionModel(BaseModel):
    __tablename__ = "knowledge_versions"
    __table_args__ = {"schema": "knowledge"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    collection_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID), default=list)
    document_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID))
    snapshot_metadata: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "knowledge"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "knowledge"}
