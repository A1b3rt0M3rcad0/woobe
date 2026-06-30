"""add provider model refs to traces

Revision ID: rai_pm_trace_refs_20260629
Revises: rai_pm_models_20260629
"""
from alembic import op
import sqlalchemy as sa


revision = "rai_pm_trace_refs_20260629"
down_revision = "rai_pm_models_20260629"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "traces",
        sa.Column("provider_model_id", sa.Uuid(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "traces",
        sa.Column("provider_credential_id", sa.Uuid(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "traces",
        sa.Column("fallback_provider_model_id", sa.Uuid(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "traces",
        sa.Column("fallback_credential_id", sa.Uuid(), nullable=True),
        schema="observability",
    )
    op.create_index(
        "ix_observability_traces_provider_model_id",
        "traces",
        ["provider_model_id"],
        schema="observability",
    )
    op.create_index(
        "ix_observability_traces_provider_credential_id",
        "traces",
        ["provider_credential_id"],
        schema="observability",
    )
    op.create_index(
        "ix_observability_traces_fallback_provider_model_id",
        "traces",
        ["fallback_provider_model_id"],
        schema="observability",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_observability_traces_fallback_provider_model_id",
        table_name="traces",
        schema="observability",
    )
    op.drop_index(
        "ix_observability_traces_provider_credential_id",
        table_name="traces",
        schema="observability",
    )
    op.drop_index(
        "ix_observability_traces_provider_model_id",
        table_name="traces",
        schema="observability",
    )
    op.drop_column("traces", "fallback_credential_id", schema="observability")
    op.drop_column("traces", "fallback_provider_model_id", schema="observability")
    op.drop_column("traces", "provider_credential_id", schema="observability")
    op.drop_column("traces", "provider_model_id", schema="observability")
