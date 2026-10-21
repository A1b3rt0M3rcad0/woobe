"""Persist server-authorized Artifact Workspace bindings on Agent Sessions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sessions",
        sa.Column("artifact_workspace_binding", postgresql.JSONB(), nullable=True),
        schema="agent",
    )
    op.create_check_constraint(
        "ck_agent_session_artifact_workspace_binding",
        "sessions",
        "artifact_workspace_binding IS NULL OR ("
        "jsonb_typeof(artifact_workspace_binding) = 'object' AND "
        "artifact_workspace_binding->>'schema_version' = '1' AND "
        "artifact_workspace_binding->>'workspace_id' ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$' AND "
        "(artifact_workspace_binding->>'catalog_version') ~ '^[0-9]+$' AND "
        "artifact_workspace_binding->>'binding_scope' IN ('session','run') AND "
        "jsonb_typeof(artifact_workspace_binding->'actions') = 'array')",
        schema="agent",
    )


def downgrade():
    op.drop_constraint(
        "ck_agent_session_artifact_workspace_binding", "sessions", schema="agent"
    )
    op.drop_column("sessions", "artifact_workspace_binding", schema="agent")
