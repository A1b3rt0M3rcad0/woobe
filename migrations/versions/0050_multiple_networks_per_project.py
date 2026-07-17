"""Allow multiple Networks per Project and add Network operational dimensions.

Revision ID: 0050
Revises: 0049
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # 0039 bound every Runtime Key to agent_id. 0043 introduced polymorphic
    # targets, but the original constraint still prevented Network Runtime Keys.
    op.drop_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        "(kind = 'project' AND agent_id IS NULL AND target_type IS NULL "
        "AND target_id IS NULL AND environment IS NULL) OR "
        "(kind = 'runtime' AND target_type = 'agent' AND target_id IS NOT NULL "
        "AND agent_id = target_id AND environment IN ('staging', 'production')) OR "
        "(kind = 'runtime' AND target_type = 'network' AND target_id IS NOT NULL "
        "AND agent_id IS NULL AND environment IN ('staging', 'production'))",
        schema="core",
    )

    op.drop_constraint(
        "uq_networks_project_id",
        "networks",
        schema="network",
        type_="unique",
    )
    op.create_index(
        "ix_networks_project_updated",
        "networks",
        ["project_id", "updated_at"],
        schema="network",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_networks_project_normalized_name
        ON network.networks (project_id, lower(btrim(name)))
        """
    )
    op.create_check_constraint(
        "ck_networks_name_not_blank",
        "networks",
        "char_length(btrim(name)) BETWEEN 1 AND 255",
        schema="network",
    )

    for column_name in (
        "network_id",
        "network_execution_id",
        "network_session_id",
        "network_version_id",
    ):
        op.add_column(
            "traces",
            sa.Column(column_name, UUID, nullable=True),
            schema="observability",
        )
    op.create_index(
        "ix_observability_traces_project_network_started",
        "traces",
        ["project_id", "network_id", "started_at"],
        schema="observability",
    )

    for column_name in (
        "network_id",
        "network_execution_id",
        "network_version_id",
    ):
        op.add_column(
            "usage_events",
            sa.Column(column_name, UUID, nullable=True),
            schema="metering",
        )
    op.create_index(
        "ix_metering_usage_events_project_network_occurred",
        "usage_events",
        ["project_id", "network_id", "occurred_at"],
        schema="metering",
    )


def downgrade() -> None:
    duplicate_project = op.get_bind().execute(
        sa.text(
            """
            SELECT project_id
            FROM network.networks
            GROUP BY project_id
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if duplicate_project is not None:
        raise RuntimeError(
            "Cannot downgrade 0050 while a Project contains multiple Networks"
        )

    network_runtime_key = op.get_bind().execute(
        sa.text(
            """
            SELECT id
            FROM core.api_keys
            WHERE kind = 'runtime'
              AND target_type = 'network'
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if network_runtime_key is not None:
        raise RuntimeError(
            "Cannot downgrade 0050 while Network Runtime Keys exist"
        )

    op.drop_index(
        "ix_metering_usage_events_project_network_occurred",
        table_name="usage_events",
        schema="metering",
    )
    for column_name in reversed(
        ("network_id", "network_execution_id", "network_version_id")
    ):
        op.drop_column("usage_events", column_name, schema="metering")

    op.drop_index(
        "ix_observability_traces_project_network_started",
        table_name="traces",
        schema="observability",
    )
    for column_name in reversed(
        (
            "network_id",
            "network_execution_id",
            "network_session_id",
            "network_version_id",
        )
    ):
        op.drop_column("traces", column_name, schema="observability")

    op.drop_constraint(
        "ck_networks_name_not_blank",
        "networks",
        schema="network",
        type_="check",
    )
    op.drop_index(
        "uq_networks_project_normalized_name",
        table_name="networks",
        schema="network",
    )
    op.drop_index(
        "ix_networks_project_updated",
        table_name="networks",
        schema="network",
    )
    op.create_unique_constraint(
        "uq_networks_project_id",
        "networks",
        ["project_id"],
        schema="network",
    )

    op.drop_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        "(kind = 'project' AND agent_id IS NULL AND environment IS NULL) OR "
        "(kind = 'runtime' AND agent_id IS NOT NULL "
        "AND environment IN ('staging', 'production'))",
        schema="core",
    )
