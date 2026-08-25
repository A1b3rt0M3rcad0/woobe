"""create Woobe instance settings

Revision ID: 0060
Revises: 0059
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instance_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("identity.users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "signup_mode",
            sa.String(length=32),
            nullable=False,
            server_default="invite_only",
        ),
        sa.Column(
            "telemetry_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
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
        sa.CheckConstraint("id = 1", name="ck_identity_instance_singleton"),
        sa.CheckConstraint(
            "signup_mode IN ('open', 'invite_only', 'disabled')",
            name="ck_identity_instance_signup_mode",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_table("instance_settings", schema="identity")
