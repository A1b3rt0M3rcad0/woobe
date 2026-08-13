"""replace Core Organizations with Instance Workspaces

Revision ID: 0061
Revises: 0060

Woobe has no production installations at this point. This migration intentionally
performs a clean model cutover instead of carrying compatibility shims for the
former multi-Organization tenancy model.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("project_invite_access", schema="core")
    op.drop_table("organization_invites", schema="identity")
    op.drop_table("organization_members", schema="identity")

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_core_workspaces"),
        sa.UniqueConstraint("slug", name="uq_core_workspaces_slug"),
        schema="core",
    )

    # Existing rows are intentionally not supported by this cutover. Clean MVP
    # databases are empty here, so replacing the ownership column is sufficient.
    with op.batch_alter_table("projects", schema="core") as batch:
        batch.drop_constraint("projects_organization_id_slug_key", type_="unique")
        batch.alter_column("organization_id", new_column_name="workspace_id")
        batch.create_foreign_key(
            "fk_core_projects_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint(
            "uq_core_projects_workspace_slug", ["workspace_id", "slug"]
        )

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["core.workspaces.id"],
            name="fk_core_workspace_members_workspace_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_core_workspace_members"),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_core_workspace_members_workspace_user"
        ),
        schema="core",
    )
    op.create_index(
        "uq_core_workspace_members_active_user",
        "workspace_members",
        ["user_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "user_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["identity.users.id"],
            name="fk_identity_user_invites_invited_by_user_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_user_invites"),
        sa.UniqueConstraint(
            "workspace_id", "email", name="uq_identity_user_invites_workspace_email"
        ),
        schema="identity",
    )
    op.create_index(
        "ix_identity_user_invites_email_status",
        "user_invites",
        ["email", "status"],
        schema="identity",
    )

    op.create_table(
        "project_invite_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_invite_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["core.projects.id"],
            name="fk_core_project_invite_access_project_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_core_project_invite_access"),
        sa.UniqueConstraint(
            "project_id", "user_invite_id", name="uq_core_project_invite_access_project_invite"
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_project_invite_access_invite_status",
        "project_invite_access", ["user_invite_id", "status"], schema="core"
    )
    op.create_index(
        "ix_core_project_invite_access_project_status",
        "project_invite_access", ["project_id", "status"], schema="core"
    )

    op.drop_table("organizations", schema="identity")

    with op.batch_alter_table("instance_settings", schema="identity") as batch:
        batch.alter_column("owner_user_id", new_column_name="admin_user_id")
        batch.add_column(sa.Column("instance_id", sa.Uuid(), nullable=True))
        batch.create_unique_constraint("uq_identity_instance_settings_instance_id", ["instance_id"])


def downgrade() -> None:
    raise RuntimeError("0061 is an intentional pre-release domain cutover and is not reversible")
