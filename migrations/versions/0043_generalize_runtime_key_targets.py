"""Generalize Runtime Keys to Agent or Network targets.

Revision ID: 0043
Revises: 0042
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("target_type", sa.String(32), nullable=True),
        schema="core",
    )
    op.add_column(
        "api_keys",
        sa.Column("target_id", UUID, nullable=True),
        schema="core",
    )
    op.execute(
        """
        UPDATE core.api_keys
        SET target_type = 'agent', target_id = agent_id
        WHERE kind = 'runtime' AND agent_id IS NOT NULL
        """
    )
    # NOT VALID keeps the rollout compatible with any legacy malformed row;
    # PostgreSQL still enforces the constraint for every new or changed row.
    op.execute(
        """
        ALTER TABLE core.api_keys
        ADD CONSTRAINT ck_core_api_keys_runtime_target
        CHECK (
            kind <> 'runtime'
            OR (target_type IN ('agent', 'network') AND target_id IS NOT NULL)
        ) NOT VALID
        """
    )
    op.create_index(
        "ix_core_api_keys_runtime_target_binding",
        "api_keys",
        [
            "project_id",
            "kind",
            "target_type",
            "target_id",
            "environment",
            "status",
        ],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_api_keys_runtime_target_binding",
        table_name="api_keys",
        schema="core",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_target",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.drop_column("api_keys", "target_id", schema="core")
    op.drop_column("api_keys", "target_type", schema="core")
