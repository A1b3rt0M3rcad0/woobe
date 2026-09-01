"""add vector snapshots

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0037"
down_revision = "0036_provider_model_trace_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vector_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="BUILDING"),
        sa.Column("embedding_provider_model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="800"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("chunking_strategy", sa.String(length=64), nullable=False, server_default="recursive_text"),
        sa.Column("parser_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["agent.document_collections.id"]),
        sa.ForeignKeyConstraint(["embedding_provider_model_id"], ["agent.provider_models.id"]),
        sa.UniqueConstraint("project_id", "collection_id", "version", name="uq_vector_snapshots_project_collection_version"),
        schema="agent",
    )
    op.create_index(
        "ix_vector_snapshots_project_collection_status",
        "vector_snapshots",
        ["project_id", "collection_id", "status"],
        schema="agent",
    )

    op.create_table(
        "vector_snapshot_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vector_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=True),
        sa.Column("document_title", sa.String(length=255), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("parser", sa.String(length=64), nullable=False),
        sa.Column("status_at_build", sa.String(length=32), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vector_snapshot_id"], ["agent.vector_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["agent.documents.id"]),
        sa.UniqueConstraint("vector_snapshot_id", "document_id", name="uq_vector_snapshot_documents_snapshot_document"),
        schema="agent",
    )
    op.create_index(
        "ix_vector_snapshot_documents_snapshot",
        "vector_snapshot_documents",
        ["vector_snapshot_id"],
        schema="agent",
    )

    op.create_table(
        "vector_snapshot_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vector_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vector_snapshot_id"], ["agent.vector_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["agent.documents.id"]),
        schema="agent",
    )
    op.create_index(
        "ix_vector_snapshot_chunks_snapshot",
        "vector_snapshot_chunks",
        ["vector_snapshot_id"],
        schema="agent",
    )
    op.create_index(
        "ix_vector_snapshot_chunks_document",
        "vector_snapshot_chunks",
        ["vector_snapshot_id", "document_id"],
        schema="agent",
    )
    op.create_index(
        "ix_vector_snapshot_chunks_embedding_hnsw",
        "vector_snapshot_chunks",
        ["embedding"],
        unique=False,
        schema="agent",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "uq_documents_active_collection_sha256",
        "documents",
        ["collection_id", "sha256"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status <> 'DELETED' AND sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_active_collection_sha256", table_name="documents", schema="agent")
    op.drop_index("ix_vector_snapshot_chunks_embedding_hnsw", table_name="vector_snapshot_chunks", schema="agent")
    op.drop_index("ix_vector_snapshot_chunks_document", table_name="vector_snapshot_chunks", schema="agent")
    op.drop_index("ix_vector_snapshot_chunks_snapshot", table_name="vector_snapshot_chunks", schema="agent")
    op.drop_table("vector_snapshot_chunks", schema="agent")
    op.drop_index("ix_vector_snapshot_documents_snapshot", table_name="vector_snapshot_documents", schema="agent")
    op.drop_table("vector_snapshot_documents", schema="agent")
    op.drop_index("ix_vector_snapshots_project_collection_status", table_name="vector_snapshots", schema="agent")
    op.drop_table("vector_snapshots", schema="agent")
