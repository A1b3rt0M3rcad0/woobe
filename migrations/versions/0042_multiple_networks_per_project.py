"""allow multiple Networks per Project and add Network operational dimensions

Revision ID: 0042
Revises: 0041
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def _column_names(schema: str, table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table, schema=schema)}


def _constraint_names(schema: str, table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    names = {
        item.get("name")
        for item in inspector.get_unique_constraints(table, schema=schema)
    }
    names.update(
        item.get("name")
        for item in inspector.get_check_constraints(table, schema=schema)
    )
    return {name for name in names if name}


def _index_names(schema: str, table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        item["name"]
        for item in inspector.get_indexes(table, schema=schema)
        if item.get("name")
    }


def upgrade() -> None:
    api_key_columns = _column_names("core", "api_keys")
    if "target_type" not in api_key_columns:
        op.add_column(
            "api_keys",
            sa.Column("target_type", sa.String(length=32), nullable=True),
            schema="core",
        )
    if "target_id" not in api_key_columns:
        op.add_column(
            "api_keys",
            sa.Column("target_id", sa.Uuid(), nullable=True),
            schema="core",
        )

    op.execute(
        """
        UPDATE core.api_keys
        SET target_type = 'agent',
            target_id = agent_id
        WHERE kind = 'runtime'
          AND agent_id IS NOT NULL
          AND (target_type IS NULL OR target_id IS NULL)
        """
    )

    api_key_constraints = _constraint_names("core", "api_keys")
    if "ck_core_api_keys_runtime_binding" in api_key_constraints:
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

    api_key_indexes = _index_names("core", "api_keys")
    if "ix_core_api_keys_runtime_target_binding" not in api_key_indexes:
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

    network_constraints = _constraint_names("network", "networks")
    if "uq_networks_project_id" in network_constraints:
        op.drop_constraint(
            "uq_networks_project_id",
            "networks",
            schema="network",
            type_="unique",
        )
    network_indexes = _index_names("network", "networks")
    if "ix_networks_project_updated" not in network_indexes:
        op.create_index(
            "ix_networks_project_updated",
            "networks",
            ["project_id", "updated_at"],
            schema="network",
        )
    if "uq_networks_project_normalized_name" not in network_indexes:
        op.execute(
            """
            CREATE UNIQUE INDEX uq_networks_project_normalized_name
            ON network.networks (project_id, lower(btrim(name)))
            """
        )
    network_constraints = _constraint_names("network", "networks")
    if "ck_networks_name_not_blank" not in network_constraints:
        op.create_check_constraint(
            "ck_networks_name_not_blank",
            "networks",
            "char_length(btrim(name)) BETWEEN 1 AND 255",
            schema="network",
        )

    trace_columns = _column_names("observability", "traces")
    for name in (
        "network_id",
        "network_execution_id",
        "network_session_id",
        "network_version_id",
    ):
        if name not in trace_columns:
            op.add_column(
                "traces",
                sa.Column(name, sa.Uuid(), nullable=True),
                schema="observability",
            )
    trace_indexes = _index_names("observability", "traces")
    if "ix_observability_traces_project_network_started" not in trace_indexes:
        op.create_index(
            "ix_observability_traces_project_network_started",
            "traces",
            ["project_id", "network_id", "started_at"],
            schema="observability",
        )

    usage_columns = _column_names("metering", "usage_events")
    for name in ("network_id", "network_execution_id", "network_version_id"):
        if name not in usage_columns:
            op.add_column(
                "usage_events",
                sa.Column(name, sa.Uuid(), nullable=True),
                schema="metering",
            )
    usage_indexes = _index_names("metering", "usage_events")
    if "ix_metering_usage_events_project_network_occurred" not in usage_indexes:
        op.create_index(
            "ix_metering_usage_events_project_network_occurred",
            "usage_events",
            ["project_id", "network_id", "occurred_at"],
            schema="metering",
        )


def downgrade() -> None:
    duplicate_projects = op.get_bind().execute(
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
    if duplicate_projects is not None:
        raise RuntimeError(
            "Cannot downgrade 0042 while a Project contains multiple Networks"
        )

    op.drop_index(
        "ix_metering_usage_events_project_network_occurred",
        table_name="usage_events",
        schema="metering",
    )
    for name in reversed(("network_id", "network_execution_id", "network_version_id")):
        op.drop_column("usage_events", name, schema="metering")

    op.drop_index(
        "ix_observability_traces_project_network_started",
        table_name="traces",
        schema="observability",
    )
    for name in reversed(
        (
            "network_id",
            "network_execution_id",
            "network_session_id",
            "network_version_id",
        )
    ):
        op.drop_column("traces", name, schema="observability")

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

    op.drop_index(
        "ix_core_api_keys_runtime_target_binding",
        table_name="api_keys",
        schema="core",
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
    op.drop_column("api_keys", "target_id", schema="core")
    op.drop_column("api_keys", "target_type", schema="core")
