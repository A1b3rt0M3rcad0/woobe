"""Durable upload identity, storage version reference and publication outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0109'
down_revision = '0108'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('uploads', sa.Column('planned_revision_id', sa.String(128)), schema='artifacts')
    # Pre-feature intents retain a stable server-owned identity on upgrade.
    op.execute('UPDATE artifacts.uploads SET planned_revision_id=id, artifact_id=COALESCE(artifact_id,id)')
    op.alter_column('uploads', 'planned_revision_id', nullable=False, schema='artifacts')
    op.add_column('revisions', sa.Column('storage_version_id', sa.String(1024)), schema='artifacts')
    op.create_table('events',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('workspace_id', sa.String(128), sa.ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('operation_id', sa.String(128), nullable=False),
        sa.Column('kind', sa.String(128), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('workspace_id', 'operation_id', 'kind', name='uq_artifact_event_operation'),
        schema='artifacts')
    op.create_index('ix_artifact_events_delivery', 'events', ['delivered_at', 'created_at', 'id'], schema='artifacts')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.uploads) OR EXISTS (SELECT 1 FROM artifacts.events) OR EXISTS (SELECT 1 FROM artifacts.revisions WHERE storage_version_id IS NOT NULL)')):
        raise RuntimeError('Durable upload receipts require a compatible reader')
    op.drop_table('events', schema='artifacts')
    op.drop_column('revisions', 'storage_version_id', schema='artifacts')
    op.drop_column('uploads', 'planned_revision_id', schema='artifacts')
