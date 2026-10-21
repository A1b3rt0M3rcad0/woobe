"""Add fenced revision and workspace retention lifecycle state.

Revision ID: 0124
Revises: 0123
"""

from alembic import op
import sqlalchemy as sa


revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workspaces",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        schema="artifacts",
    )
    op.add_column(
        "workspaces",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="artifacts",
    )
    op.execute(
        "UPDATE artifacts.workspaces SET archived_at = now() "
        "WHERE status = 'archived' AND archived_at IS NULL"
    )
    op.create_index(
        "ix_artifact_workspace_retention",
        "workspaces",
        ["status", "archived_at", "id"],
        schema="artifacts",
    )
    op.add_column(
        "revisions",
        sa.Column(
            "content_state",
            sa.String(length=32),
            server_default="available",
            nullable=False,
        ),
        schema="artifacts",
    )
    op.create_check_constraint(
        "ck_artifact_revision_content_state",
        "revisions",
        "content_state IN ('available','deletion_pending','purged')",
        schema="artifacts",
    )
    op.create_index(
        "ix_artifact_revision_retention",
        "revisions",
        ["workspace_id", "content_state", "created_at", "id"],
        schema="artifacts",
    )


def downgrade():
    op.drop_index("ix_artifact_revision_retention", table_name="revisions", schema="artifacts")
    op.drop_constraint("ck_artifact_revision_content_state", "revisions", schema="artifacts", type_="check")
    op.drop_column("revisions", "content_state", schema="artifacts")
    op.drop_index("ix_artifact_workspace_retention", table_name="workspaces", schema="artifacts")
    op.drop_column("workspaces", "deletion_requested_at", schema="artifacts")
    op.drop_column("workspaces", "archived_at", schema="artifacts")
