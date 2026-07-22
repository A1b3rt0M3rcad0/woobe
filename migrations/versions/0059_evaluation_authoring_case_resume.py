"""add resumable evaluation authoring cases

Revision ID: 0059
Revises: 0058
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

UUID = sa.Uuid
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "authoring_attempts",
        sa.Column("id", UUID(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "authoring_call_id",
            UUID(),
            sa.ForeignKey("evaluation.authoring_calls.id"),
            nullable=False,
        ),
        sa.Column(
            "authoring_batch_id",
            UUID(),
            sa.ForeignKey("evaluation.authoring_batches.id"),
            nullable=True,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("provider_model_id", UUID(), nullable=False),
        sa.Column("provider_credential_id", UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "requested_slot_ids",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 10), nullable=True),
        sa.Column("pricing_snapshot", JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=128), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_attempts_call_created",
        "authoring_attempts",
        ["authoring_call_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_attempts_project_status",
        "authoring_attempts",
        ["project_id", "status", "created_at"],
        schema="evaluation",
    )

    op.create_table(
        "authoring_case_slots",
        sa.Column("id", UUID(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "authoring_call_id",
            UUID(),
            sa.ForeignKey("evaluation.authoring_calls.id"),
            nullable=False,
        ),
        sa.Column(
            "authoring_batch_id",
            UUID(),
            sa.ForeignKey("evaluation.authoring_batches.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("coverage_category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("generated_case", JSONB(), nullable=True),
        sa.Column("validation_result", JSONB(), nullable=True),
        sa.Column("failure_category", sa.String(length=128), nullable=True),
        sa.Column("recommended_action", sa.String(length=128), nullable=True),
        sa.Column(
            "source_attempt_id",
            UUID(),
            sa.ForeignKey("evaluation.authoring_attempts.id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "authoring_call_id",
            "position",
            name="uq_evaluation_authoring_case_slots_position",
        ),
        sa.CheckConstraint(
            "position > 0",
            name="ck_evaluation_authoring_case_slots_position",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_case_slots_call_status",
        "authoring_case_slots",
        ["authoring_call_id", "status", "position"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_case_slots_batch_position",
        "authoring_case_slots",
        ["authoring_batch_id", "position"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_authoring_case_slots_batch_position",
        table_name="authoring_case_slots",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_authoring_case_slots_call_status",
        table_name="authoring_case_slots",
        schema="evaluation",
    )
    op.drop_table("authoring_case_slots", schema="evaluation")

    op.drop_index(
        "ix_evaluation_authoring_attempts_project_status",
        table_name="authoring_attempts",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_authoring_attempts_call_created",
        table_name="authoring_attempts",
        schema="evaluation",
    )
    op.drop_table("authoring_attempts", schema="evaluation")
