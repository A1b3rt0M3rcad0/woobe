"""Make Agent Staging snapshots immutable and explicit.

Revision ID: 0045
Revises: 0044
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_releases",
        sa.Column("snapshot_kind", sa.String(length=16), nullable=True),
        schema="agent",
    )
    op.execute(
        """
        UPDATE agent.agent_releases
        SET snapshot_kind = CASE
            WHEN status = 'draft' THEN 'draft'
            WHEN status = 'staging' THEN 'staging'
            WHEN status IN ('production', 'rolled_back') THEN 'release'
            WHEN status = 'archived' AND version = 'draft' THEN 'draft'
            WHEN status = 'archived' AND version LIKE 'staging%' THEN 'staging'
            ELSE 'release'
        END
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY agent_id
                       ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
                   ) AS position
            FROM agent.agent_releases
            WHERE status = 'staging'
        )
        UPDATE agent.agent_releases AS releases
        SET status = 'archived'
        FROM ranked
        WHERE releases.id = ranked.id AND ranked.position > 1
        """
    )
    op.alter_column(
        "agent_releases",
        "snapshot_kind",
        nullable=False,
        server_default=sa.text("'draft'"),
        schema="agent",
    )

    # Some existing databases already carry this index from the previous
    # Agent schema lifecycle. Rebuild it deterministically after normalizing
    # duplicate active Staging rows instead of failing on the relation name.
    op.execute("DROP INDEX IF EXISTS agent.uq_agent_releases_staging")
    op.create_index(
        "uq_agent_releases_staging",
        "agent_releases",
        ["agent_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'staging'"),
    )
    op.create_check_constraint(
        "ck_agent_releases_snapshot_kind",
        "agent_releases",
        "snapshot_kind IN ('draft', 'staging', 'release')",
        schema="agent",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_releases_snapshot_kind",
        "agent_releases",
        schema="agent",
        type_="check",
    )
    op.execute("DROP INDEX IF EXISTS agent.uq_agent_releases_staging")
    op.drop_column("agent_releases", "snapshot_kind", schema="agent")
