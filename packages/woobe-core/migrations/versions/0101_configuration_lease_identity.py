"""Fence configuration lease retries to the accepted dependency closure."""
from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade():
    # Unknown historical identities fail closed on retry, never repin material.
    op.execute("ALTER TABLE core.project_configuration_leases ADD COLUMN dependency_digest varchar(64) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE core.project_configuration_leases ALTER COLUMN dependency_digest DROP DEFAULT")


def downgrade():
    raise RuntimeError("Configuration lease identity requires a forward-compatible rollback")
