"""add project memberships

Revision ID: 0056
Revises: 0055
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
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
            name="fk_core_project_members_project_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_core_project_members"),
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_core_project_members_project_user",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_project_members_user_status",
        "project_members",
        ["user_id", "status"],
        schema="core",
    )
    op.create_index(
        "ix_core_project_members_project_status",
        "project_members",
        ["project_id", "status"],
        schema="core",
    )

    # Preserve the access non-owner members already had before Project-level
    # isolation is enabled. Workspace owners keep implicit access and do not
    # need duplicated Project memberships. New Projects do not inherit members.
    op.execute(
        """
        INSERT INTO core.project_members
            (id, project_id, user_id, status, granted_by_user_id, created_at, updated_at)
        SELECT gen_random_uuid(), p.id, wm.user_id, 'active', NULL, now(), now()
        FROM core.projects AS p
        JOIN identity.workspace_members AS wm
          ON wm.workspace_id = p.workspace_id
         AND wm.status = 'active'
         AND wm.role <> 'owner'
        ON CONFLICT (project_id, user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_project_members_project_status",
        table_name="project_members",
        schema="core",
    )
    op.drop_index(
        "ix_core_project_members_user_status",
        table_name="project_members",
        schema="core",
    )
    op.drop_table("project_members", schema="core")
