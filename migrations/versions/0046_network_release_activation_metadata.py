"""Add auditable Network Production activation metadata.

Revision ID: 0046
Revises: 0045
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "network_versions",
        sa.Column("source_version_id", UUID, nullable=True),
        schema="network",
    )
    op.add_column(
        "network_versions",
        sa.Column("activation_kind", sa.String(length=32), nullable=True),
        schema="network",
    )
    op.add_column(
        "network_versions",
        sa.Column("change_description", sa.Text(), nullable=True),
        schema="network",
    )
    op.create_foreign_key(
        "fk_network_versions_source_version",
        "network_versions",
        "network_versions",
        ["source_version_id"],
        ["id"],
        source_schema="network",
        referent_schema="network",
    )
    op.create_check_constraint(
        "ck_network_versions_activation_kind",
        "network_versions",
        "activation_kind IS NULL OR activation_kind IN ('publish', 'reactivate', 'rollback')",
        schema="network",
    )
    op.execute(
        """
        UPDATE network.network_versions
        SET source_version_id = rollback_of_version_id,
            activation_kind = CASE
                WHEN rollback_of_version_id IS NOT NULL THEN 'rollback'
                WHEN kind = 'release' THEN 'publish'
                ELSE NULL
            END
        WHERE source_version_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_network_versions_activation_kind",
        "network_versions",
        schema="network",
        type_="check",
    )
    op.drop_constraint(
        "fk_network_versions_source_version",
        "network_versions",
        schema="network",
        type_="foreignkey",
    )
    op.drop_column("network_versions", "change_description", schema="network")
    op.drop_column("network_versions", "activation_kind", schema="network")
    op.drop_column("network_versions", "source_version_id", schema="network")
