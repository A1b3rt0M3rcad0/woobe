"""normalize legacy Agent Session statuses

Revision ID: 0061
Revises: 0060
"""

from __future__ import annotations

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

VALID_SESSION_STATUSES = (
    "active",
    "waiting",
    "idle",
    "closed",
    "expired",
    "error",
)
_SQL_SESSION_STATUSES = ", ".join(f"'{status}'" for status in VALID_SESSION_STATUSES)


def upgrade() -> None:
    # Historical Session rows used `archived`, but the current domain models a
    # non-operational historical Session as `closed`. Normalize the known
    # legacy value before enforcing the current domain contract.
    op.execute(
        """
        UPDATE agent.sessions
        SET status = 'closed'
        WHERE LOWER(status) = 'archived'
        """
    )

    # Keep known values canonical in case an older installation persisted an
    # uppercase/mixed-case representation of a current SessionStatus value.
    op.execute(
        f"""
        UPDATE agent.sessions
        SET status = LOWER(status)
        WHERE LOWER(status) IN ({_SQL_SESSION_STATUSES})
        """
    )

    # Unknown values intentionally make this migration fail instead of being
    # silently coerced. That keeps persisted state aligned with SessionStatus.
    op.create_check_constraint(
        "ck_agent_sessions_status",
        "sessions",
        f"status IN ({_SQL_SESSION_STATUSES})",
        schema="agent",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_sessions_status",
        "sessions",
        schema="agent",
        type_="check",
    )
    # Data normalization is intentionally one-way: a `closed` Session cannot be
    # distinguished safely from a row that was historically `archived`.
