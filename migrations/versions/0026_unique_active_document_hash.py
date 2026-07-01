"""prevent duplicate active document hashes per project

Revision ID: 0026
Revises: 0025
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_agent_documents_project_sha256_active"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "documents",
        ["project_id", "sha256"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("sha256 IS NOT NULL AND status <> 'deleted'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="documents", schema="agent")
