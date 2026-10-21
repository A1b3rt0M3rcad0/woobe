"""Persist accepted Network Artifact bindings and runtime principal snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "network_sessions",
        sa.Column("artifact_workspace_binding", postgresql.JSONB(), nullable=True),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("artifact_workspace_binding", postgresql.JSONB(), nullable=True),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("runtime_principal_snapshot", postgresql.JSONB(), nullable=True),
        schema="network",
    )
    op.create_check_constraint(
        "ck_network_session_artifact_workspace_binding",
        "network_sessions",
        "artifact_workspace_binding IS NULL OR ("
        "jsonb_typeof(artifact_workspace_binding) = 'object' AND "
        "artifact_workspace_binding->>'schema_version' = '1' AND "
        "artifact_workspace_binding->>'workspace_id' ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$' AND "
        "(artifact_workspace_binding->>'catalog_version') ~ '^[0-9]+$' AND "
        "artifact_workspace_binding->>'binding_scope' IN ('session','run') AND "
        "jsonb_typeof(artifact_workspace_binding->'actions') = 'array')",
        schema="network",
    )
    op.create_check_constraint(
        "ck_network_execution_artifact_runtime_snapshot",
        "network_executions",
        "(artifact_workspace_binding IS NULL OR ("
        "jsonb_typeof(artifact_workspace_binding) = 'object' AND "
        "artifact_workspace_binding->>'schema_version' = '1' AND "
        "artifact_workspace_binding->>'workspace_id' ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$' AND "
        "(artifact_workspace_binding->>'catalog_version') ~ '^[0-9]+$' AND "
        "artifact_workspace_binding->>'binding_scope' IN ('session','run') AND "
        "jsonb_typeof(artifact_workspace_binding->'actions') = 'array')) AND "
        "(artifact_workspace_binding IS NULL OR runtime_principal_snapshot IS NOT NULL) AND "
        "(runtime_principal_snapshot IS NULL OR jsonb_typeof(runtime_principal_snapshot) = 'object')",
        schema="network",
    )


def downgrade():
    op.drop_constraint(
        "ck_network_execution_artifact_runtime_snapshot",
        "network_executions",
        schema="network",
    )
    op.drop_constraint(
        "ck_network_session_artifact_workspace_binding",
        "network_sessions",
        schema="network",
    )
    op.drop_column("network_executions", "runtime_principal_snapshot", schema="network")
    op.drop_column("network_executions", "artifact_workspace_binding", schema="network")
    op.drop_column("network_sessions", "artifact_workspace_binding", schema="network")
