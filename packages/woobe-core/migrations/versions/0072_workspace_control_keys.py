"""Add Workspace-scoped control-plane API keys and Project grants.

Revision ID: 0072
Revises: 0071
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_control_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_control_key_id", sa.Uuid(), nullable=True),
        sa.Column("rotated_from_id", sa.Uuid(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_core_workspace_control_keys"),
        sa.UniqueConstraint("key_hash", name="uq_core_workspace_control_keys_key_hash"),
        schema="core",
    )
    op.create_index(
        "ix_core_workspace_control_keys_prefix_version",
        "workspace_control_keys",
        ["key_prefix", "key_version"],
        schema="core",
    )
    op.create_index(
        "ix_core_workspace_control_keys_workspace_status",
        "workspace_control_keys",
        ["workspace_id", "status"],
        schema="core",
    )
    op.create_index(
        "ix_core_workspace_control_keys_credential_created",
        "workspace_control_keys",
        ["credential_id", "created_at"],
        schema="core",
    )

    op.create_table(
        "workspace_control_key_project_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_key_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(
            ["control_key_id"],
            ["core.workspace_control_keys.id"],
            name="fk_core_control_key_grants_key_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["core.projects.id"],
            name="fk_core_control_key_grants_project_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_core_workspace_control_key_project_grants"),
        sa.UniqueConstraint(
            "control_key_id",
            "project_id",
            name="uq_core_control_key_project_grant",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_control_key_grants_project",
        "workspace_control_key_project_grants",
        ["project_id", "control_key_id"],
        schema="core",
    )

    op.alter_column(
        "api_keys",
        "created_by_user_id",
        schema="core",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.add_column(
        "api_keys",
        sa.Column("created_by_control_key_id", sa.Uuid(), nullable=True),
        schema="core",
    )
    op.create_foreign_key(
        "fk_core_api_keys_created_by_control_key_id",
        "api_keys",
        "workspace_control_keys",
        ["created_by_control_key_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_core_api_keys_created_by_control_key_id",
        "api_keys",
        schema="core",
        type_="foreignkey",
    )
    op.drop_column(
        "api_keys",
        "created_by_control_key_id",
        schema="core",
    )
    op.execute(
        "DELETE FROM core.api_keys WHERE created_by_user_id IS NULL"
    )
    op.alter_column(
        "api_keys",
        "created_by_user_id",
        schema="core",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.drop_index(
        "ix_core_control_key_grants_project",
        table_name="workspace_control_key_project_grants",
        schema="core",
    )
    op.drop_table("workspace_control_key_project_grants", schema="core")
    op.drop_index(
        "ix_core_workspace_control_keys_credential_created",
        table_name="workspace_control_keys",
        schema="core",
    )
    op.drop_index(
        "ix_core_workspace_control_keys_workspace_status",
        table_name="workspace_control_keys",
        schema="core",
    )
    op.drop_index(
        "ix_core_workspace_control_keys_prefix_version",
        table_name="workspace_control_keys",
        schema="core",
    )
    op.drop_table("workspace_control_keys", schema="core")
