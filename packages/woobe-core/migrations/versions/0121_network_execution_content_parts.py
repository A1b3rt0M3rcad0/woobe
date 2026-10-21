"""Persist typed Network input parts through execution and rerun."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "network_executions",
        sa.Column(
            "input_content_parts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="network",
    )


def downgrade():
    op.drop_column("network_executions", "input_content_parts", schema="network")
