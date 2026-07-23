"""separate operational and evaluation runtime usage

Revision ID: 0066
Revises: 0065
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "network_executions",
        sa.Column(
            "run_purpose",
            sa.String(length=32),
            nullable=False,
            server_default="operational",
        ),
        schema="network",
    )
    for name in (
        "evaluation_run_id",
        "evaluation_trial_id",
        "evaluation_target_id",
    ):
        op.add_column(
            "network_executions",
            sa.Column(name, postgresql.UUID(as_uuid=True), nullable=True),
            schema="network",
        )
    op.add_column(
        "network_executions",
        sa.Column("target_snapshot_hash", sa.String(length=64), nullable=True),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("target_snapshot_label", sa.String(length=32), nullable=True),
        schema="network",
    )

    op.execute(
        """
        UPDATE network.network_executions execution
        SET
            run_purpose = 'evaluation',
            evaluation_run_id = trial.evaluation_run_id,
            evaluation_trial_id = trial.id,
            evaluation_target_id = trial.evaluation_target_id,
            target_snapshot_hash = target.snapshot_hash,
            target_snapshot_label = target.environment
        FROM evaluation.trials trial
        JOIN evaluation.targets target
          ON target.id = trial.evaluation_target_id
        WHERE trial.network_execution_id = execution.id
        """
    )
    op.execute(
        """
        UPDATE network.network_executions execution
        SET run_purpose = 'evaluation'
        FROM network.network_sessions session
        WHERE session.id = execution.network_session_id
          AND session.tenant_id = 'evaluation'
          AND execution.run_purpose = 'operational'
        """
    )

    for schema, table in (
        ("observability", "traces"),
        ("metering", "usage_events"),
        ("network", "network_executions"),
    ):
        op.create_check_constraint(
            f"ck_{table}_run_purpose",
            table,
            "run_purpose IN ('operational', 'evaluation')",
            schema=schema,
        )

    op.create_index(
        "ix_network_executions_project_purpose_created",
        "network_executions",
        ["project_id", "run_purpose", "created_at"],
        schema="network",
    )
    op.create_index(
        "ix_network_executions_evaluation_run",
        "network_executions",
        ["evaluation_run_id", "evaluation_trial_id"],
        schema="network",
        postgresql_where=sa.text("evaluation_run_id IS NOT NULL"),
    )

    op.execute(
        """
        INSERT INTO metering.usage_events (
            id, project_id, agent_id, network_id, network_execution_id,
            network_version_id, source_event_id, occurred_at, trace_id, call_id,
            environment, run_purpose, evaluation_run_id, evaluation_trial_id,
            comparison_pair_id, target_side, agent_release_id,
            agent_release_version, provider, model, provider_model_id,
            event_type, quantity, unit, input_tokens, output_tokens, cost_usd,
            cost_status, cost_reason, usage_complete, pricing_snapshot, data,
            created_at, updated_at
        )
        SELECT
            model_call.id,
            model_call.project_id,
            NULL,
            NULL,
            NULL,
            NULL,
            model_call.id,
            COALESCE(
                model_call.completed_at,
                model_call.started_at,
                model_call.created_at
            ),
            NULL,
            model_call.id::text,
            NULL,
            'evaluation',
            model_call.evaluation_run_id,
            model_call.evaluation_trial_id,
            NULL,
            NULL,
            NULL,
            NULL,
            model_call.provider,
            model_call.model,
            model_call.provider_model_id,
            'evaluation_model_call',
            1.0,
            'model_call',
            model_call.input_tokens,
            model_call.output_tokens,
            model_call.cost_usd,
            model_call.cost_status,
            model_call.cost_reason,
            (
                model_call.input_tokens IS NOT NULL
                AND model_call.output_tokens IS NOT NULL
            ),
            model_call.pricing_snapshot,
            jsonb_build_object(
                'usage_category', 'quality_assurance',
                'usage_subtype', 'judge',
                'evaluation_role', 'judge',
                'migration_backfill', true
            ),
            model_call.created_at,
            model_call.updated_at
        FROM evaluation.model_calls model_call
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM metering.usage_events
        WHERE event_type = 'evaluation_model_call'
          AND data ->> 'migration_backfill' = 'true'
        """
    )
    op.drop_index(
        "ix_network_executions_evaluation_run",
        table_name="network_executions",
        schema="network",
    )
    op.drop_index(
        "ix_network_executions_project_purpose_created",
        table_name="network_executions",
        schema="network",
    )
    for schema, table in (
        ("network", "network_executions"),
        ("metering", "usage_events"),
        ("observability", "traces"),
    ):
        op.drop_constraint(
            f"ck_{table}_run_purpose",
            table,
            schema=schema,
            type_="check",
        )
    for name in (
        "target_snapshot_label",
        "target_snapshot_hash",
        "evaluation_target_id",
        "evaluation_trial_id",
        "evaluation_run_id",
        "run_purpose",
    ):
        op.drop_column("network_executions", name, schema="network")
