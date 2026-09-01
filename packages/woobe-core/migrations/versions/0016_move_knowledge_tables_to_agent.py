"""move knowledge business tables to agent schema (SET SCHEMA) with compat views

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-16
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS agent")
    # document_collections
    op.execute("ALTER TABLE knowledge.document_collections SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW knowledge.document_collections AS SELECT * FROM agent.document_collections")
    # agent_collections
    op.execute("ALTER TABLE knowledge.agent_collections SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW knowledge.agent_collections AS SELECT * FROM agent.agent_collections")
    # documents
    op.execute("ALTER TABLE knowledge.documents SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW knowledge.documents AS SELECT * FROM agent.documents")
    # document_chunks
    op.execute("ALTER TABLE knowledge.document_chunks SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW knowledge.document_chunks AS SELECT * FROM agent.document_chunks")
    # knowledge_versions
    op.execute("ALTER TABLE knowledge.knowledge_versions SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW knowledge.knowledge_versions AS SELECT * FROM agent.knowledge_versions")


def downgrade() -> None:
    # knowledge_versions
    op.execute("DROP VIEW IF EXISTS knowledge.knowledge_versions")
    op.execute("ALTER TABLE agent.knowledge_versions SET SCHEMA knowledge")
    # document_chunks
    op.execute("DROP VIEW IF EXISTS knowledge.document_chunks")
    op.execute("ALTER TABLE agent.document_chunks SET SCHEMA knowledge")
    # documents
    op.execute("DROP VIEW IF EXISTS knowledge.documents")
    op.execute("ALTER TABLE agent.documents SET SCHEMA knowledge")
    # agent_collections
    op.execute("DROP VIEW IF EXISTS knowledge.agent_collections")
    op.execute("ALTER TABLE agent.agent_collections SET SCHEMA knowledge")
    # document_collections
    op.execute("DROP VIEW IF EXISTS knowledge.document_collections")
    op.execute("ALTER TABLE agent.document_collections SET SCHEMA knowledge")
