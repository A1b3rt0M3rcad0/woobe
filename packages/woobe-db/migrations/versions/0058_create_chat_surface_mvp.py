"""create ChatSurface distribution boundary

Revision ID: 0058
Revises: 0057
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS chat_surface")
    op.create_table(
        "chat_surfaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "environment",
            sa.String(length=16),
            nullable=False,
            server_default="production",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "access_mode",
            sa.String(length=32),
            nullable=False,
            server_default="backend_managed",
        ),
        sa.Column(
            "allowed_origins",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "appearance_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "requests_per_minute",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column(
            "max_concurrent_runs",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
        sa.Column(
            "session_token_ttl_seconds",
            sa.Integer(),
            nullable=False,
            server_default="900",
        ),
        sa.Column(
            "token_epoch",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "target_type IN ('agent', 'network')",
            name="ck_chat_surface_target_type",
        ),
        sa.CheckConstraint(
            "environment = 'production'",
            name="ck_chat_surface_production_only",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'disabled', 'archived')",
            name="ck_chat_surface_status",
        ),
        sa.CheckConstraint(
            "session_token_ttl_seconds BETWEEN 60 AND 3600",
            name="ck_chat_surface_token_ttl",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["core.projects.id"],
            name="fk_chat_surface_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_surface"),
        sa.UniqueConstraint("public_id", name="uq_chat_surface_public_id"),
        sa.UniqueConstraint(
            "project_id",
            "normalized_name",
            name="uq_chat_surface_project_name",
        ),
        schema="chat_surface",
    )
    op.create_index(
        "ix_chat_surface_project_status",
        "chat_surfaces",
        ["project_id", "status", "created_at"],
        schema="chat_surface",
    )
    op.create_index(
        "ix_chat_surface_target",
        "chat_surfaces",
        ["project_id", "target_type", "target_id", "status"],
        schema="chat_surface",
    )

    op.create_table(
        "session_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_surface_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("surface_credential_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "target_type IN ('agent', 'network')",
            name="ck_chat_surface_session_target_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'blocked')",
            name="ck_chat_surface_session_status",
        ),
        sa.ForeignKeyConstraint(
            ["chat_surface_id"],
            ["chat_surface.chat_surfaces.id"],
            name="fk_chat_surface_session_surface",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_surface_session"),
        sa.UniqueConstraint(
            "chat_surface_id",
            "session_id",
            name="uq_chat_surface_session",
        ),
        sa.UniqueConstraint(
            "chat_surface_id",
            "idempotency_key",
            name="uq_chat_surface_session_idempotency",
        ),
        schema="chat_surface",
    )
    op.create_index(
        "ix_chat_surface_session_activity",
        "session_bindings",
        ["chat_surface_id", "status", "updated_at"],
        schema="chat_surface",
    )

    op.create_table(
        "message_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_binding_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="accepted",
        ),
        sa.Column("target_run_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('accepted', 'streaming', 'completed', 'failed', 'cancelled')",
            name="ck_chat_surface_message_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_binding_id"],
            ["chat_surface.session_bindings.id"],
            name="fk_chat_surface_message_session",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_surface_message_request"),
        sa.UniqueConstraint(
            "session_binding_id",
            "idempotency_key",
            name="uq_chat_surface_message_idempotency",
        ),
        schema="chat_surface",
    )
    op.create_index(
        "uq_chat_surface_active_message",
        "message_requests",
        ["session_binding_id"],
        unique=True,
        schema="chat_surface",
        postgresql_where=sa.text("status IN ('accepted', 'streaming')"),
    )

    op.add_column(
        "api_keys",
        sa.Column("chat_surface_id", sa.Uuid(), nullable=True),
        schema="core",
    )
    op.create_index(
        "ix_core_api_keys_chat_surface",
        "api_keys",
        ["project_id", "kind", "chat_surface_id", "status"],
        schema="core",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_target",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_interfaces",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_binding",
        "api_keys",
        "(kind = 'project' AND agent_id IS NULL AND target_type IS NULL "
        "AND target_id IS NULL AND chat_surface_id IS NULL AND environment IS NULL) OR "
        "(kind = 'runtime' AND target_type = 'agent' AND target_id IS NOT NULL "
        "AND agent_id = target_id AND chat_surface_id IS NULL "
        "AND environment IN ('staging', 'production')) OR "
        "(kind = 'runtime' AND target_type = 'network' AND target_id IS NOT NULL "
        "AND agent_id IS NULL AND chat_surface_id IS NULL "
        "AND environment IN ('staging', 'production')) OR "
        "(kind = 'chat_surface' AND agent_id IS NULL AND target_type IS NULL "
        "AND target_id IS NULL AND chat_surface_id IS NOT NULL "
        "AND environment IS NULL)",
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_target",
        "api_keys",
        "kind <> 'runtime' OR "
        "(target_type IN ('agent', 'network') AND target_id IS NOT NULL)",
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_interfaces",
        "api_keys",
        "(kind <> 'runtime' OR jsonb_array_length(interfaces) > 0) AND "
        "(kind <> 'chat_surface' OR jsonb_array_length(interfaces) = 0)",
        schema="core",
    )

    for schema, table in (
        ("agent", "sessions"),
        ("network", "network_sessions"),
    ):
        op.add_column(
            table,
            sa.Column("chat_surface_id", sa.Uuid(), nullable=True),
            schema=schema,
        )
        op.add_column(
            table,
            sa.Column(
                "origin",
                sa.String(length=32),
                nullable=False,
                server_default="runtime_api",
            ),
            schema=schema,
        )
        op.create_index(
            f"ix_{schema}_sessions_chat_surface",
            table,
            ["chat_surface_id", "status", "last_message_at"],
            schema=schema,
        )


def downgrade() -> None:
    for schema, table in (
        ("network", "network_sessions"),
        ("agent", "sessions"),
    ):
        op.drop_index(
            f"ix_{schema}_sessions_chat_surface",
            table_name=table,
            schema=schema,
        )
        op.drop_column(table, "origin", schema=schema)
        op.drop_column(table, "chat_surface_id", schema=schema)

    op.drop_constraint(
        "ck_core_api_keys_runtime_interfaces",
        "api_keys",
        schema="core",
        type_="check",
    )
    op.drop_constraint(
        "ck_core_api_keys_runtime_target",
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
    op.create_check_constraint(
        "ck_core_api_keys_runtime_target",
        "api_keys",
        "kind <> 'runtime' OR "
        "(target_type IN ('agent', 'network') AND target_id IS NOT NULL)",
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_api_keys_runtime_interfaces",
        "api_keys",
        "kind <> 'runtime' OR jsonb_array_length(interfaces) > 0",
        schema="core",
    )
    op.drop_index(
        "ix_core_api_keys_chat_surface",
        table_name="api_keys",
        schema="core",
    )
    op.drop_column("api_keys", "chat_surface_id", schema="core")

    op.drop_index(
        "uq_chat_surface_active_message",
        table_name="message_requests",
        schema="chat_surface",
    )
    op.drop_table("message_requests", schema="chat_surface")
    op.drop_index(
        "ix_chat_surface_session_activity",
        table_name="session_bindings",
        schema="chat_surface",
    )
    op.drop_table("session_bindings", schema="chat_surface")
    op.drop_index(
        "ix_chat_surface_target",
        table_name="chat_surfaces",
        schema="chat_surface",
    )
    op.drop_index(
        "ix_chat_surface_project_status",
        table_name="chat_surfaces",
        schema="chat_surface",
    )
    op.drop_table("chat_surfaces", schema="chat_surface")
    op.execute("DROP SCHEMA IF EXISTS chat_surface")
