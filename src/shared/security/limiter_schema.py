from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


def upgrade() -> None:
    op.create_table(
        "security_rate_limit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("subject_key", sa.String(length=255), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_security_rate_limit_events_window",
        "security_rate_limit_events",
        ["namespace", "subject_key", "occurred_at"],
        unique=False,
        schema="core",
    )
    op.create_table(
        "security_concurrency_leases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("subject_key", sa.String(length=255), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_security_concurrency_leases_subject",
        "security_concurrency_leases",
        ["namespace", "subject_key", "expires_at"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "ix_security_concurrency_leases_expiry",
        "security_concurrency_leases",
        ["expires_at"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_security_concurrency_leases_expiry",
        table_name="security_concurrency_leases",
        schema="core",
    )
    op.drop_index(
        "ix_security_concurrency_leases_subject",
        table_name="security_concurrency_leases",
        schema="core",
    )
    op.drop_table("security_concurrency_leases", schema="core")
    op.drop_index(
        "ix_security_rate_limit_events_window",
        table_name="security_rate_limit_events",
        schema="core",
    )
    op.drop_table("security_rate_limit_events", schema="core")
