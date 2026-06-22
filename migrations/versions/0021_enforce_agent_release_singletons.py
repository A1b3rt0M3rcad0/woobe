"""enforce per-agent release lifecycle singletons

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY agent_id, status
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM agent.agent_releases
            WHERE status IN ('draft', 'staging')
        )
        UPDATE agent.agent_releases AS r
        SET status = 'archived',
            release_notes = concat_ws(E'\n', r.release_notes, 'Archived by migration 0021: duplicate draft/staging singleton.')
        FROM ranked
        WHERE r.id = ranked.id
          AND ranked.rn > 1;
        """
    )
    op.create_index(
        "uq_agent_releases_draft",
        "agent_releases",
        ["agent_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_agent_releases_staging",
        "agent_releases",
        ["agent_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'staging'"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_releases_staging", table_name="agent_releases", schema="agent")
    op.drop_index("uq_agent_releases_draft", table_name="agent_releases", schema="agent")
