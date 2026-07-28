"""add pending Project access for Organization invitations

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_invite_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_invite_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
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
            ["project_id"],
            ["core.projects.id"],
            name="fk_core_project_invite_access_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_invite_id"],
            ["identity.organization_invites.id"],
            name="fk_core_project_invite_access_invite_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_core_project_invite_access"),
        sa.UniqueConstraint(
            "project_id",
            "organization_invite_id",
            name="uq_core_project_invite_access_project_invite",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_project_invite_access_invite_status",
        "project_invite_access",
        ["organization_invite_id", "status"],
        schema="core",
    )
    op.create_index(
        "ix_core_project_invite_access_project_status",
        "project_invite_access",
        ["project_id", "status"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_project_invite_access_project_status",
        table_name="project_invite_access",
        schema="core",
    )
    op.drop_index(
        "ix_core_project_invite_access_invite_status",
        table_name="project_invite_access",
        schema="core",
    )
    op.drop_table("project_invite_access", schema="core")
