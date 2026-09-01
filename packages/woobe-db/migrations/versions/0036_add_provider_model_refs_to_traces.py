"""add provider model refs to traces

Revision ID: 0036_provider_model_trace_refs
Revises: 0035_provider_models
"""
from alembic import op
import sqlalchemy as sa


revision = "0036_provider_model_trace_refs"
down_revision = "0035_provider_models"
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
