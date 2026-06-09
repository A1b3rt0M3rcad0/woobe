"""create agent versioning tables: prompts, contracts, model configs, releases, tests, knowledge versions

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ai.agent_prompts
    op.create_table(
        "agent_prompts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["core.projects.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai.agents.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["identity.users.id"]),
        schema="ai",
    )
    op.create_index("ix_agent_prompts_agent_version", "agent_prompts", ["agent_id", "version"], unique=True, schema="ai")

    # ai.agent_contracts
    op.create_table(
        "agent_contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("input_schema", postgresql.JSONB(), nullable=True),
        sa.Column("output_schema", postgresql.JSONB(), nullable=True),
        sa.Column("validation_mode", sa.String(16), nullable=False, server_default=sa.text("'loose'")),
        sa.Column("repair_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("additional_instructions", sa.Text(), nullable=True),
        sa.Column("schema_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["core.projects.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai.agents.id"]),
        schema="ai",
    )
    op.create_index("ix_agent_contracts_agent_version", "agent_contracts", ["agent_id", "version"], unique=True, schema="ai")

    # ai.agent_model_configs
    op.create_table(
        "agent_model_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_credential_id", sa.Uuid(), nullable=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("session_mode", sa.String(32), nullable=True),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["core.projects.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai.agents.id"]),
        sa.ForeignKeyConstraint(["provider_credential_id"], ["ai.provider_credentials.id"]),
        schema="ai",
    )
    op.create_index("ix_agent_model_configs_agent_version", "agent_model_configs", ["agent_id", "version"], unique=True, schema="ai")

    # knowledge.knowledge_versions (must be created before agent_releases which references it)
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("collection_ids", postgresql.ARRAY(sa.Uuid()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("document_ids", postgresql.ARRAY(sa.Uuid()), nullable=True),
        sa.Column("snapshot_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["core.projects.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai.agents.id"]),
        schema="knowledge",
    )
    op.create_index("ix_knowledge_versions_agent_version", "knowledge_versions", ["agent_id", "version"], unique=True, schema="knowledge")

    # ai.agent_releases
    op.create_table(
        "agent_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("prompt_version_id", sa.Uuid(), nullable=True),
        sa.Column("contract_version_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_version_id", sa.Uuid(), nullable=True),
        sa.Column("model_config_version_id", sa.Uuid(), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("promoted_by", sa.Uuid(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["core.projects.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai.agents.id"]),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["ai.agent_prompts.id"]),
        sa.ForeignKeyConstraint(["contract_version_id"], ["ai.agent_contracts.id"]),
        sa.ForeignKeyConstraint(["knowledge_version_id"], ["knowledge.knowledge_versions.id"]),
        sa.ForeignKeyConstraint(["model_config_version_id"], ["ai.agent_model_configs.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["identity.users.id"]),
        sa.ForeignKeyConstraint(["promoted_by"], ["identity.users.id"]),
        schema="ai",
    )
    op.create_index("ix_agent_releases_agent_version", "agent_releases", ["agent_id", "version"], unique=True, schema="ai")
    op.create_index("ix_agent_releases_agent_status", "agent_releases", ["agent_id", "status"], schema="ai")

    # ai.agent_release_tests
    op.create_table(
        "agent_release_tests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("contract_version_id", sa.Uuid(), nullable=True),
        sa.Column("input_payload", postgresql.JSONB(), nullable=True),
        sa.Column("expected_output", postgresql.JSONB(), nullable=True),
        sa.Column("actual_output", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("validation_errors", postgresql.JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["core.projects.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai.agents.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["ai.agent_releases.id"]),
        sa.ForeignKeyConstraint(["contract_version_id"], ["ai.agent_contracts.id"]),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_table("agent_release_tests", schema="ai")
    op.drop_table("agent_releases", schema="ai")
    op.drop_table("agent_model_configs", schema="ai")
    op.drop_table("agent_contracts", schema="ai")
    op.drop_table("agent_prompts", schema="ai")
    op.drop_table("knowledge_versions", schema="knowledge")
