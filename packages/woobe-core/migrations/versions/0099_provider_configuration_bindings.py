"""Expand Provider bindings while preserving credential identity."""
from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE agent.provider_credentials ALTER COLUMN encrypted_secret DROP NOT NULL, ADD COLUMN authentication jsonb, ADD COLUMN binding_revision integer NOT NULL DEFAULT 1")


def downgrade():
    raise RuntimeError("Provider references cannot be discarded; use a forward migration")
