"""harden project API keys

Revision ID: 0026
Revises: 0025

Existing keys are explicitly marked as version 0. Their original secret cannot be
recovered and the runtime authentication pipeline accepts only version 1 keys.
"""

import sqlalchemy as sa

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("key_version", sa.SmallInteger(), nullable=True),
        schema="core",
    )
    op.execute("UPDATE core.api_keys SET key_version = 0 WHERE key_version IS NULL")
    op.alter_column(
        "api_keys",
        "key_version",
        existing_type=sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("1"),
        schema="core",
    )
    op.add_column(
        "api_keys",
        sa.Column("rotated_from_id", sa.Uuid(), nullable=True),
        schema="core",
    )
    op.create_foreign_key(
        "fk_core_api_keys_rotated_from_id",
        source_table="api_keys",
        referent_table="api_keys",
        local_cols=["rotated_from_id"],
        remote_cols=["id"],
        source_schema="core",
        referent_schema="core",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_core_api_keys_prefix_status",
        "api_keys",
        ["key_prefix", "status"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_api_keys_prefix_status",
        table_name="api_keys",
        schema="core",
    )
    op.drop_constraint(
        "fk_core_api_keys_rotated_from_id",
        "api_keys",
        schema="core",
        type_="foreignkey",
    )
    op.drop_column("api_keys", "rotated_from_id", schema="core")
    op.drop_column("api_keys", "key_version", schema="core")
