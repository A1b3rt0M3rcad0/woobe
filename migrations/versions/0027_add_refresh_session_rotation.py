"""add refresh session rotation metadata

Revision ID: 0027
Revises: 0026
"""

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column("replaced_by_session_id", sa.Uuid(), nullable=True),
        schema="identity",
    )
    op.create_foreign_key(
        "fk_identity_user_sessions_replaced_by",
        source_table="user_sessions",
        referent_table="user_sessions",
        local_cols=["replaced_by_session_id"],
        remote_cols=["id"],
        source_schema="identity",
        referent_schema="identity",
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_identity_user_sessions_refresh_token_hash",
        "user_sessions",
        ["refresh_token_hash"],
        schema="identity",
    )
    op.create_index(
        "ix_identity_user_sessions_user_id",
        "user_sessions",
        ["user_id"],
        schema="identity",
    )
    op.create_index(
        "ix_identity_user_sessions_expires_at",
        "user_sessions",
        ["expires_at"],
        schema="identity",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identity_user_sessions_expires_at",
        table_name="user_sessions",
        schema="identity",
    )
    op.drop_index(
        "ix_identity_user_sessions_user_id",
        table_name="user_sessions",
        schema="identity",
    )
    op.drop_constraint(
        "uq_identity_user_sessions_refresh_token_hash",
        "user_sessions",
        schema="identity",
        type_="unique",
    )
    op.drop_constraint(
        "fk_identity_user_sessions_replaced_by",
        "user_sessions",
        schema="identity",
        type_="foreignkey",
    )
    op.drop_column("user_sessions", "replaced_by_session_id", schema="identity")
