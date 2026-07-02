"""add reusable provider models

Revision ID: 0035_provider_models
Revises: 0034_noop
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0035_provider_models"
down_revision = "0034_noop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("provider_credential_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["provider_credential_id"],
            ["agent.provider_credentials.id"],
            name="provider_models_provider_credential_id_fkey",
        ),
        sa.UniqueConstraint(
            "project_id",
            "provider_credential_id",
            "model",
            name="uq_provider_models_project_credential_model",
        ),
        schema="agent",
    )
    op.create_index(
        "ix_provider_models_project_id",
        "provider_models",
        ["project_id"],
        schema="agent",
    )
    op.create_index(
        "ix_provider_models_credential_id",
        "provider_models",
        ["provider_credential_id"],
        schema="agent",
    )
    op.add_column(
        "agents",
        sa.Column("provider_model_id", sa.Uuid(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "agents",
        sa.Column("fallback_provider_model_id", sa.Uuid(), nullable=True),
        schema="agent",
    )
    op.create_foreign_key(
        "agents_provider_model_id_fkey",
        "agents",
        "provider_models",
        ["provider_model_id"],
        ["id"],
        source_schema="agent",
        referent_schema="agent",
    )
    op.create_foreign_key(
        "agents_fallback_provider_model_id_fkey",
        "agents",
        "provider_models",
        ["fallback_provider_model_id"],
        ["id"],
        source_schema="agent",
        referent_schema="agent",
    )
    op.add_column(
        "agent_releases",
        sa.Column("provider_model_id", sa.Uuid(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "agent_releases",
        sa.Column("fallback_provider_model_id", sa.Uuid(), nullable=True),
        schema="agent",
    )
    op.create_foreign_key(
        "agent_releases_provider_model_id_fkey",
        "agent_releases",
        "provider_models",
        ["provider_model_id"],
        ["id"],
        source_schema="agent",
        referent_schema="agent",
    )
    op.create_foreign_key(
        "agent_releases_fallback_provider_model_id_fkey",
        "agent_releases",
        "provider_models",
        ["fallback_provider_model_id"],
        ["id"],
        source_schema="agent",
        referent_schema="agent",
    )


def downgrade() -> None:
    op.drop_constraint(
        "agent_releases_fallback_provider_model_id_fkey",
        "agent_releases",
        schema="agent",
        type_="foreignkey",
    )
    op.drop_constraint(
        "agent_releases_provider_model_id_fkey",
        "agent_releases",
        schema="agent",
        type_="foreignkey",
    )
    op.drop_column("agent_releases", "fallback_provider_model_id", schema="agent")
    op.drop_column("agent_releases", "provider_model_id", schema="agent")
    op.drop_constraint(
        "agents_fallback_provider_model_id_fkey",
        "agents",
        schema="agent",
        type_="foreignkey",
    )
    op.drop_constraint(
        "agents_provider_model_id_fkey",
        "agents",
        schema="agent",
        type_="foreignkey",
    )
    op.drop_column("agents", "fallback_provider_model_id", schema="agent")
    op.drop_column("agents", "provider_model_id", schema="agent")
    op.drop_index("ix_provider_models_credential_id", table_name="provider_models", schema="agent")
    op.drop_index("ix_provider_models_project_id", table_name="provider_models", schema="agent")
    op.drop_table("provider_models", schema="agent")
