"""prevent duplicate active document hashes per project

Revision ID: rai_doc_hash_20260701
Revises: rai_pm_models_20260629
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "rai_doc_hash_20260701"
down_revision = "rai_pm_models_20260629"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_agent_documents_project_sha256_active"

DUPLICATE_CHECK_SQL = sa.text(
    """
    SELECT project_id, sha256, count(*) AS duplicate_count
    FROM agent.documents
    WHERE sha256 IS NOT NULL
      AND status <> 'deleted'
    GROUP BY project_id, sha256
    HAVING count(*) > 1
    LIMIT 10
    """
)


def upgrade() -> None:
    duplicate_rows = op.get_bind().execute(DUPLICATE_CHECK_SQL).mappings().all()
    if duplicate_rows:
        details = "; ".join(
            f"project_id={row['project_id']} sha256={row['sha256']} count={row['duplicate_count']}"
            for row in duplicate_rows
        )
        raise RuntimeError(
            "Cannot create unique active document hash index because duplicate active "
            f"documents already exist: {details}"
        )

    op.create_index(
        INDEX_NAME,
        "documents",
        ["project_id", "sha256"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("sha256 IS NOT NULL AND status <> 'deleted'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="documents", schema="agent")
