"""add runtime key bindings

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="project"),
        schema="core",
    )
    op.add_column(
        "api_keys",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="core",
    )
    op.add_column(
        "api_keys",
        sa.Column("environment", sa.String(length=32), nullable=True),
        schema="core",
    )
    op.add_column(
        "api_keys",
        sa.Column(
            "interfaces",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        "(kind = 'project' AND agent_id IS NULL AND environment IS NULL) OR "
        "(kind = 'runtime' AND agent_id IS NOT NULL AND environment IN ('staging', 'production'))",
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_interfaces",
        "api_keys",
        "kind <> 'runtime' OR jsonb_array_length(interfaces) > 0",
        schema="core",
    )
    op.create_index(
        "ix_core_api_keys_runtime_binding",
        "api_keys",
        ["project_id", "kind", "agent_id", "environment", "status"],
        unique=False,
        schema="core",
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
        UPDATE agent.agent_releases
        SET status = 'archived'
        WHERE id IN (SELECT id FROM ranked WHERE position > 1)
        """
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
    op.drop_index(
        "uq_agent_releases_staging",
        table_name="agent_releases",
        schema="agent",
    )
    op.drop_index(
        "ix_core_api_keys_runtime_binding",
        table_name="api_keys",
        schema="core",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_interfaces",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.drop_column("api_keys", "interfaces", schema="core")
    op.drop_column("api_keys", "environment", schema="core")
    op.drop_column("api_keys", "agent_id", schema="core")
    op.drop_column("api_keys", "kind", schema="core")
