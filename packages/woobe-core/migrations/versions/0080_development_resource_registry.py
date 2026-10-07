"""Agent optimistic revisions and scoped development resource identities.

Revision ID: 0080
Revises: 0079
"""

from alembic import op
import sqlalchemy as sa

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agents",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        schema="agent",
    )
    op.create_table(
        "resource_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
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
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("registry_id", sa.Uuid(), nullable=False),
        sa.Column("resource_uid", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("definition_digest", sa.String(64), nullable=True),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.UniqueConstraint(
            "project_id",
            "registry_id",
            "resource_uid",
            name="uq_package_resource_binding",
        ),
        schema="package",
    )


def downgrade():
    op.drop_table("resource_bindings", schema="package")
    op.drop_column("agents", "revision", schema="agent")
