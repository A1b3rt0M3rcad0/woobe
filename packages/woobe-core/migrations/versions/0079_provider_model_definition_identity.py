"""Identify installed Models by their complete native ModelSpec.

Revision ID: 0079
Revises: 0078
"""

from alembic import op

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "uq_provider_models_project_credential_model",
        "provider_models",
        schema="agent",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_models_project_credential_spec",
        "provider_models",
        ["project_id", "provider_credential_id", "model", "spec_hash"],
        schema="agent",
    )


def downgrade():
    # PostgreSQL rejects downgrade if distinct definitions share the old identity.
    # Never delete or rewrite installed Model definitions to force a downgrade.
    op.create_unique_constraint(
        "uq_provider_models_project_credential_model",
        "provider_models",
        ["project_id", "provider_credential_id", "model"],
        schema="agent",
    )
    op.drop_constraint(
        "uq_provider_models_project_credential_spec",
        "provider_models",
        schema="agent",
        type_="unique",
    )
