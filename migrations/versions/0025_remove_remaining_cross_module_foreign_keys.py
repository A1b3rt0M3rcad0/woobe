"""remove remaining cross-module Foreign Key constraints

Drops FKs from:
- core -> identity (workspace_id, created_by_user_id)
- billing -> identity (workspace_id x2)
- metering -> core (project_id x3)
- observability -> core (project_id x2)

Revision ID: 0025
Revises: 0024
"""
from sqlalchemy import text

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

CROSS_MODULE_FKS: list[tuple[str, str, str, str]] = [
    # (schema, table, column, FK constraint name)
    ("core", "projects", "workspace_id", "projects_workspace_id_fkey"),
    ("core", "api_keys", "created_by_user_id", "api_keys_created_by_user_id_fkey"),
    ("billing", "customers", "workspace_id", "customers_workspace_id_fkey"),
    ("billing", "subscriptions", "workspace_id", "subscriptions_workspace_id_fkey"),
    ("metering", "usage_events", "project_id", "usage_events_project_id_fkey"),
    ("metering", "usage_daily_project", "project_id", "usage_daily_project_project_id_fkey"),
    ("metering", "usage_daily_agent", "project_id", "usage_daily_agent_project_id_fkey"),
    ("observability", "traces", "project_id", "traces_project_id_fkey"),
    ("observability", "trace_events", "project_id", "trace_events_project_id_fkey"),
]


def upgrade() -> None:
    for schema, table, column, fk_name in CROSS_MODULE_FKS:
        _drop_fk_if_exists(schema, table, fk_name)


def downgrade() -> None:
    # Restore core -> identity FKs
    op.create_foreign_key(
        "projects_workspace_id_fkey",
        source_table="projects", referent_table="identity.workspaces",
        local_cols=["workspace_id"], remote_cols=["id"],
        source_schema="core",
    )
    op.create_foreign_key(
        "api_keys_created_by_user_id_fkey",
        source_table="api_keys", referent_table="identity.users",
        local_cols=["created_by_user_id"], remote_cols=["id"],
        source_schema="core",
    )
    # Restore billing -> identity FKs
    op.create_foreign_key(
        "customers_workspace_id_fkey",
        source_table="customers", referent_table="identity.workspaces",
        local_cols=["workspace_id"], remote_cols=["id"],
        source_schema="billing",
    )
    op.create_foreign_key(
        "subscriptions_workspace_id_fkey",
        source_table="subscriptions", referent_table="identity.workspaces",
        local_cols=["workspace_id"], remote_cols=["id"],
        source_schema="billing",
    )
    # Restore metering -> core FKs
    op.create_foreign_key(
        "usage_events_project_id_fkey",
        source_table="usage_events", referent_table="core.projects",
        local_cols=["project_id"], remote_cols=["id"],
        source_schema="metering",
    )
    op.create_foreign_key(
        "usage_daily_project_project_id_fkey",
        source_table="usage_daily_project", referent_table="core.projects",
        local_cols=["project_id"], remote_cols=["id"],
        source_schema="metering",
    )
    op.create_foreign_key(
        "usage_daily_agent_project_id_fkey",
        source_table="usage_daily_agent", referent_table="core.projects",
        local_cols=["project_id"], remote_cols=["id"],
        source_schema="metering",
    )
    # Restore observability -> core FKs
    op.create_foreign_key(
        "traces_project_id_fkey",
        source_table="traces", referent_table="core.projects",
        local_cols=["project_id"], remote_cols=["id"],
        source_schema="observability",
    )
    op.create_foreign_key(
        "trace_events_project_id_fkey",
        source_table="trace_events", referent_table="core.projects",
        local_cols=["project_id"], remote_cols=["id"],
        source_schema="observability",
    )


def _drop_fk_if_exists(schema: str, table: str, fk_name: str) -> None:
    conn = op.get_bind()
    result = conn.execute(
        text(
            "SELECT 1 FROM pg_constraint "
            "WHERE conname = :fk_name AND connamespace::regnamespace::text = :schema"
        ),
        {"fk_name": fk_name, "schema": schema},
    )
    if result.fetchone():
        op.drop_constraint(fk_name, table_name=table, schema=schema, type_="foreignkey")
