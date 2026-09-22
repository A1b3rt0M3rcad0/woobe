"""Add project-scoped environment keys and per-environment values.

Revision ID: 0070
Revises: 0069
"""

from alembic import op


revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE core.project_environment_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES core.projects(id) ON DELETE CASCADE,
            key VARCHAR(128) NOT NULL,
            kind VARCHAR(16) NOT NULL DEFAULT 'value',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_core_project_environment_keys_project_key
                UNIQUE (project_id, key),
            CONSTRAINT ck_core_project_environment_keys_kind
                CHECK (kind IN ('value', 'secret'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_core_project_environment_keys_project
        ON core.project_environment_keys (project_id, key)
        """
    )
    op.execute(
        """
        CREATE TABLE core.project_environment_values (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_id UUID NOT NULL
                REFERENCES core.project_environment_keys(id) ON DELETE CASCADE,
            environment VARCHAR(16) NOT NULL,
            stored_value TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_core_project_environment_values_key_environment
                UNIQUE (key_id, environment),
            CONSTRAINT ck_core_project_environment_values_environment
                CHECK (environment IN ('draft', 'staging', 'production'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_core_project_environment_values_key_environment
        ON core.project_environment_values (key_id, environment)
        """
    )


def downgrade() -> None:
    op.drop_table("project_environment_values", schema="core")
    op.drop_table("project_environment_keys", schema="core")
