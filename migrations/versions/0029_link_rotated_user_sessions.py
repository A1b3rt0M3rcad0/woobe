"""link rotated refresh sessions

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column(
            "replaced_by_session_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="identity",
    )
    op.create_foreign_key(
        "fk_identity_user_sessions_replaced_by",
        "user_sessions",
        "user_sessions",
        ["replaced_by_session_id"],
        ["id"],
        source_schema="identity",
        referent_schema="identity",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_identity_user_sessions_replaced_by_session_id",
        "user_sessions",
        ["replaced_by_session_id"],
        unique=False,
        schema="identity",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identity_user_sessions_replaced_by_session_id",
        table_name="user_sessions",
        schema="identity",
    )
    op.drop_constraint(
        "fk_identity_user_sessions_replaced_by",
        "user_sessions",
        schema="identity",
        type_="foreignkey",
    )
    op.drop_column(
        "user_sessions",
        "replaced_by_session_id",
        schema="identity",
    )
