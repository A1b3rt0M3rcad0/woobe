"""Enable live Draft sessions with immutable execution snapshots.

Revision ID: 0044
Revises: 0043
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.alter_column(
        "network_sessions",
        "network_version_id",
        nullable=True,
        schema="network",
    )
    op.alter_column(
        "network_executions",
        "network_version_id",
        nullable=True,
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("draft_revision", sa.Integer(), nullable=True),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("definition_snapshot", JSONB, nullable=True),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("resolved_bindings_snapshot", JSONB, nullable=True),
        schema="network",
    )
    op.create_check_constraint(
        "ck_network_sessions_environment_version",
        "network_sessions",
        "(environment = 'draft' AND network_version_id IS NULL) OR "
        "(environment IN ('staging', 'production') AND network_version_id IS NOT NULL)",
        schema="network",
    )
    op.create_check_constraint(
        "ck_network_executions_snapshot_source",
        "network_executions",
        "(network_version_id IS NULL AND draft_revision IS NOT NULL "
        "AND definition_snapshot IS NOT NULL "
        "AND resolved_bindings_snapshot IS NOT NULL) OR "
        "(network_version_id IS NOT NULL AND draft_revision IS NULL)",
        schema="network",
    )
    op.create_index(
        "ix_network_executions_network_draft_revision",
        "network_executions",
        ["network_id", "draft_revision", "created_at"],
        schema="network",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_network_executions_network_draft_revision",
        table_name="network_executions",
        schema="network",
    )
    op.drop_constraint(
        "ck_network_executions_snapshot_source",
        "network_executions",
        schema="network",
        type_="check",
    )
    op.drop_constraint(
        "ck_network_sessions_environment_version",
        "network_sessions",
        schema="network",
        type_="check",
    )
    op.drop_column("network_executions", "resolved_bindings_snapshot", schema="network")
    op.drop_column("network_executions", "definition_snapshot", schema="network")
    op.drop_column("network_executions", "draft_revision", schema="network")
    op.alter_column(
        "network_executions",
        "network_version_id",
        nullable=False,
        schema="network",
    )
    op.alter_column(
        "network_sessions",
        "network_version_id",
        nullable=False,
        schema="network",
    )
