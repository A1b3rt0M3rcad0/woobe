"""noop redundant agent release production unique index

Revision ID: 0032_release_prod_index_noop
Revises: 0031_agent_release_lifecycle

The production partial unique index is created by migration 0010 while the table
still lives in the legacy ai schema. Later schema-consolidation migrations move
that table, and its indexes, into the agent schema. Re-creating the same index
here breaks clean database upgrades with DuplicateTableError.
"""

revision = "0032_release_prod_index_noop"
down_revision = "0031_agent_release_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
