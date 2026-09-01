"""add logical API key credentials and editable metadata

Revision ID: 0040
Revises: 0039
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        schema="core",
    )
    op.add_column(
        "api_keys",
        sa.Column("description", sa.String(length=500), nullable=True),
        schema="core",
    )

    connection = op.get_bind()
    connection.execute(
        text(
            """
            WITH RECURSIVE credential_chains AS (
                SELECT id, id AS credential_id
                FROM core.api_keys
                WHERE rotated_from_id IS NULL

                UNION ALL

                SELECT child.id, parent.credential_id
                FROM core.api_keys AS child
                JOIN credential_chains AS parent
                  ON child.rotated_from_id = parent.id
            )
            UPDATE core.api_keys AS api_key
            SET credential_id = chain.credential_id
            FROM credential_chains AS chain
            WHERE api_key.id = chain.id
            """
        )
    )
    connection.execute(
        text("UPDATE core.api_keys SET credential_id = id WHERE credential_id IS NULL")
    )

    op.alter_column(
        "api_keys",
        "credential_id",
        nullable=False,
        schema="core",
    )
    op.create_index(
        "ix_core_api_keys_credential_created",
        "api_keys",
        ["credential_id", "created_at"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_api_keys_credential_created",
        table_name="api_keys",
        schema="core",
    )
    op.drop_column("api_keys", "description", schema="core")
    op.drop_column("api_keys", "credential_id", schema="core")
