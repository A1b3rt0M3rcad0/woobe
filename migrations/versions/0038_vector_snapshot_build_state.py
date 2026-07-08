"""add vector snapshot build state

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vector_snapshots", sa.Column("build_stage", sa.String(length=32), nullable=False, server_default="QUEUED"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("build_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="agent")
    op.add_column("vector_snapshots", sa.Column("build_config_hash", sa.String(length=64), nullable=True), schema="agent")
    op.add_column("vector_snapshots", sa.Column("vector_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("total_document_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("processed_document_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("total_chunk_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("processed_chunk_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("embedded_chunk_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.add_column("vector_snapshots", sa.Column("current_document_id", postgresql.UUID(as_uuid=True), nullable=True), schema="agent")
    op.add_column("vector_snapshots", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True), schema="agent")
    op.add_column("vector_snapshots", sa.Column("locked_by", sa.String(length=128), nullable=True), schema="agent")
    op.add_column("vector_snapshots", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), schema="agent")
    op.create_index(
        "uq_vector_snapshots_building_per_collection",
        "vector_snapshots",
        ["collection_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'BUILDING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_vector_snapshots_building_per_collection", table_name="vector_snapshots", schema="agent")
    op.drop_column("vector_snapshots", "attempt_count", schema="agent")
    op.drop_column("vector_snapshots", "locked_by", schema="agent")
    op.drop_column("vector_snapshots", "locked_at", schema="agent")
    op.drop_column("vector_snapshots", "current_document_id", schema="agent")
    op.drop_column("vector_snapshots", "embedded_chunk_count", schema="agent")
    op.drop_column("vector_snapshots", "processed_chunk_count", schema="agent")
    op.drop_column("vector_snapshots", "total_chunk_count", schema="agent")
    op.drop_column("vector_snapshots", "processed_document_count", schema="agent")
    op.drop_column("vector_snapshots", "total_document_count", schema="agent")
    op.drop_column("vector_snapshots", "vector_count", schema="agent")
    op.drop_column("vector_snapshots", "build_config_hash", schema="agent")
    op.drop_column("vector_snapshots", "build_config", schema="agent")
    op.drop_column("vector_snapshots", "build_stage", schema="agent")
