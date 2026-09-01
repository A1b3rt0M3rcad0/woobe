"""move ai business tables to agent schema (SET SCHEMA) with compat views

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-16
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS agent")
    # provider_credentials
    op.execute("ALTER TABLE ai.provider_credentials SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.provider_credentials AS SELECT * FROM agent.provider_credentials")
    # agents
    op.execute("ALTER TABLE ai.agents SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.agents AS SELECT * FROM agent.agents")
    # agent_prompts
    op.execute("ALTER TABLE ai.agent_prompts SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.agent_prompts AS SELECT * FROM agent.agent_prompts")
    # agent_contracts
    op.execute("ALTER TABLE ai.agent_contracts SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.agent_contracts AS SELECT * FROM agent.agent_contracts")
    # agent_model_configs
    op.execute("ALTER TABLE ai.agent_model_configs SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.agent_model_configs AS SELECT * FROM agent.agent_model_configs")
    # agent_releases
    op.execute("ALTER TABLE ai.agent_releases SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.agent_releases AS SELECT * FROM agent.agent_releases")
    # agent_release_tests
    op.execute("ALTER TABLE ai.agent_release_tests SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW ai.agent_release_tests AS SELECT * FROM agent.agent_release_tests")


def downgrade() -> None:
    # agent_release_tests
    op.execute("DROP VIEW IF EXISTS ai.agent_release_tests")
    op.execute("ALTER TABLE agent.agent_release_tests SET SCHEMA ai")
    # agent_releases
    op.execute("DROP VIEW IF EXISTS ai.agent_releases")
    op.execute("ALTER TABLE agent.agent_releases SET SCHEMA ai")
    # agent_model_configs
    op.execute("DROP VIEW IF EXISTS ai.agent_model_configs")
    op.execute("ALTER TABLE agent.agent_model_configs SET SCHEMA ai")
    # agent_contracts
    op.execute("DROP VIEW IF EXISTS ai.agent_contracts")
    op.execute("ALTER TABLE agent.agent_contracts SET SCHEMA ai")
    # agent_prompts
    op.execute("DROP VIEW IF EXISTS ai.agent_prompts")
    op.execute("ALTER TABLE agent.agent_prompts SET SCHEMA ai")
    # agents
    op.execute("DROP VIEW IF EXISTS ai.agents")
    op.execute("ALTER TABLE agent.agents SET SCHEMA ai")
    # provider_credentials
    op.execute("DROP VIEW IF EXISTS ai.provider_credentials")
    op.execute("ALTER TABLE agent.provider_credentials SET SCHEMA ai")
