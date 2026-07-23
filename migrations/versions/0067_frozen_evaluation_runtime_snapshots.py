"""execute Evaluations from frozen runtime snapshots

Revision ID: 0067
Revises: 0066
"""

from __future__ import annotations

from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_network_executions_snapshot_source",
        "network_executions",
        schema="network",
        type_="check",
    )
    op.create_check_constraint(
        "ck_network_executions_snapshot_source",
        "network_executions",
        "((definition_snapshot IS NULL AND resolved_bindings_snapshot IS NULL) "
        "OR (definition_snapshot IS NOT NULL "
        "AND resolved_bindings_snapshot IS NOT NULL)) "
        "AND ((network_version_id IS NULL AND draft_revision IS NOT NULL "
        "AND definition_snapshot IS NOT NULL) "
        "OR (network_version_id IS NOT NULL AND draft_revision IS NULL))",
        schema="network",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_network_executions_snapshot_source",
        "network_executions",
        schema="network",
        type_="check",
    )
    op.execute(
        """
        UPDATE network.network_executions
        SET definition_snapshot = NULL,
            resolved_bindings_snapshot = NULL
        WHERE network_version_id IS NOT NULL
        """
    )
    op.create_check_constraint(
        "ck_network_executions_snapshot_source",
        "network_executions",
        "(network_version_id IS NULL AND draft_revision IS NOT NULL "
        "AND definition_snapshot IS NOT NULL "
        "AND resolved_bindings_snapshot IS NOT NULL) OR "
        "(network_version_id IS NOT NULL AND draft_revision IS NULL)",
        schema="network",
    )
