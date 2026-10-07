"""Retain committed preparation identities across failed development operations."""

from alembic import op
import sqlalchemy as sa

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "resource_bindings",
        sa.Column("preparation", sa.JSON(), nullable=False, server_default="{}"),
        schema="package",
    )


def downgrade():
    op.drop_column("resource_bindings", "preparation", schema="package")
