"""Preserve delegated credential expiration across human and machine rotations.

Revision ID: 0077
Revises: 0076
"""

import sqlalchemy as sa
from alembic import op

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "api_keys",
        sa.Column("delegation_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="core",
    )
    op.execute("""
        UPDATE core.api_keys AS child
        SET delegation_expires_at = LEAST(parent.expires_at, parent.delegation_expires_at)
        FROM core.workspace_control_keys AS parent
        WHERE child.created_by_control_key_id = parent.id
    """)


def downgrade():
    op.drop_column("api_keys", "delegation_expires_at", schema="core")
