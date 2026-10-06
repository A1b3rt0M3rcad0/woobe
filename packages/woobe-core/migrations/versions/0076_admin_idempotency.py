"""Add transaction-bound administrative replay records.

Revision ID: 0076
Revises: 0075
"""

import sqlalchemy as sa
from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "administrative_operations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(96), nullable=False),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("key_digest", sa.LargeBinary(), nullable=False),
        sa.Column("payload_digest", sa.LargeBinary(), nullable=False),
        sa.Column("response_ciphertext", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "actor",
            "operation",
            "key_digest",
            name="uq_core_administrative_operation",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_administrative_operation_expiry",
        "administrative_operations",
        ["expires_at"],
        schema="core",
    )


def downgrade():
    op.drop_table("administrative_operations", schema="core")
