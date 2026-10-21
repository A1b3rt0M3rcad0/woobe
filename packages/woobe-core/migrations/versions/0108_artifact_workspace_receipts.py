"""Retain the original Workspace creation fingerprint across metadata changes."""
from alembic import op
import sqlalchemy as sa

revision = '0108'
down_revision = '0107'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('workspaces', sa.Column('creation_fingerprint', sa.String(64), nullable=True), schema='artifacts')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.workspaces WHERE creation_fingerprint IS NOT NULL)')):
        raise RuntimeError('Artifact Workspace creation receipts require a compatible reader')
    op.drop_column('workspaces', 'creation_fingerprint', schema='artifacts')
