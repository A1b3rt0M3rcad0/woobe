"""File operation receipts and immutable publication provenance."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0110'
down_revision = '0109'
branch_labels = None
depends_on = None


def upgrade():
    for name in ('operation_id', 'run_id', 'node_id'):
        op.add_column('revisions', sa.Column(name, sa.String(128)), schema='artifacts')
    op.add_column('uploads', sa.Column('origin', sa.String(32), nullable=False, server_default='upload'), schema='artifacts')
    for name in ('run_id', 'node_id'):
        op.add_column('uploads', sa.Column(name, sa.String(128)), schema='artifacts')
    op.create_table('catalog_operations',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('workspace_id', sa.String(128), sa.ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('principal_id', sa.String(128), nullable=False),
        sa.Column('operation_id', sa.String(128), nullable=False),
        sa.Column('request_fingerprint', sa.String(64), nullable=False),
        sa.Column('receipt', postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'operation_id', name='uq_artifact_catalog_operation'), schema='artifacts')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.catalog_operations) OR EXISTS (SELECT 1 FROM artifacts.revisions WHERE operation_id IS NOT NULL OR run_id IS NOT NULL OR node_id IS NOT NULL) OR EXISTS (SELECT 1 FROM artifacts.uploads WHERE origin <> :original OR run_id IS NOT NULL OR node_id IS NOT NULL)'), {'original': 'upload'}):
        raise RuntimeError('File mutation receipts require a compatible reader')
    op.drop_table('catalog_operations', schema='artifacts')
    for name in ('run_id', 'node_id', 'origin'):
        op.drop_column('uploads', name, schema='artifacts')
    for name in ('operation_id', 'run_id', 'node_id'):
        op.drop_column('revisions', name, schema='artifacts')
