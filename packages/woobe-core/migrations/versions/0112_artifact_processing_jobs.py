"""Durable artifact jobs, fenced attempts and existing outbox/inbox contracts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0112'
down_revision = '0111'
branch_labels = None
depends_on = None


def event_columns():
    return [sa.Column('id', postgresql.UUID(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('aggregate_type', sa.String(128), nullable=False),
        sa.Column('event_type', sa.String(255), nullable=False),
        sa.Column('event_version', sa.Integer(), nullable=False),
        sa.Column('routing_key', sa.String(255), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('correlation_id', postgresql.UUID()), sa.Column('causation_id', postgresql.UUID()),
        sa.Column('status', sa.String(32), nullable=False), sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('locked_at', sa.DateTime(timezone=True)), sa.Column('locked_by', sa.String(128)),
        sa.Column('error', sa.Text())]


def upgrade():
    op.create_unique_constraint('uq_artifact_workspace_scope_identity', 'workspaces', ['project_id', 'environment', 'id'], schema='artifacts')
    op.create_table('processing_project_queue',
        sa.Column('project_id', postgresql.UUID(), primary_key=True),
        sa.Column('last_claim_at', sa.DateTime(timezone=True)), schema='artifacts')
    op.create_table('processing_workspace_queue',
        sa.Column('workspace_id', sa.String(128), sa.ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('last_claim_at', sa.DateTime(timezone=True)), schema='artifacts')
    op.create_table('processing_jobs',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('project_id', postgresql.UUID(), nullable=False),
        sa.Column('environment', sa.String(16), nullable=False),
        sa.Column('workspace_id', sa.String(128), sa.ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('artifact_id', sa.String(128), nullable=False), sa.Column('revision_id', sa.String(128), nullable=False),
        sa.Column('principal_id', sa.String(128), nullable=False), sa.Column('principal_snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('operation_id', sa.String(128), nullable=False), sa.Column('request_fingerprint', sa.String(64), nullable=False),
        sa.Column('processing_fingerprint', sa.String(64), nullable=False),
        sa.Column('profile_id', sa.String(128)), sa.Column('profile_revision', sa.BigInteger()),
        sa.Column('recipe', postgresql.JSONB(), nullable=False), sa.Column('recipe_fingerprint', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False), sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False), sa.Column('fencing_token', sa.BigInteger(), nullable=False),
        sa.Column('worker_id', sa.String(128)), sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('cancel_requested_at', sa.DateTime(timezone=True)),
        sa.Column('checkpoints', postgresql.JSONB(), nullable=False), sa.Column('result', postgresql.JSONB()),
        sa.Column('error_code', sa.String(128)), sa.Column('retryable', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'operation_id', name='uq_artifact_processing_operation'),
        sa.ForeignKeyConstraint(['project_id', 'environment', 'workspace_id'], ['artifacts.workspaces.project_id', 'artifacts.workspaces.environment', 'artifacts.workspaces.id'], name='fk_artifact_job_scope'),
        sa.ForeignKeyConstraint(['workspace_id', 'artifact_id'], ['artifacts.artifacts.workspace_id', 'artifacts.artifacts.id'], name='fk_artifact_job_owner'),
        sa.ForeignKeyConstraint(['artifact_id', 'revision_id'], ['artifacts.revisions.artifact_id', 'artifacts.revisions.id'], name='fk_artifact_job_source'),
        sa.ForeignKeyConstraint(['project_id', 'environment', 'profile_id', 'profile_revision'], ['artifacts.processing_profiles.project_id', 'artifacts.processing_profiles.environment', 'artifacts.processing_profiles.id', 'artifacts.processing_profiles.revision'], name='fk_artifact_job_profile'),
        sa.CheckConstraint('(profile_id IS NULL) = (profile_revision IS NULL)', name='ck_artifact_job_profile_pair'),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancel_requested','cancelled','uncertain')", name='ck_artifact_job_status'),
        sa.CheckConstraint('attempt >= 0 AND fencing_token >= 0 AND max_attempts >= 1', name='ck_artifact_job_attempt'), schema='artifacts')
    op.create_index('ix_artifact_processing_expired_lease', 'processing_jobs', ['status', 'lease_until', 'id'], schema='artifacts')
    op.create_index('ix_artifact_processing_claim', 'processing_jobs', ['status', 'available_at', 'created_at', 'id'], schema='artifacts')
    op.create_index('ix_artifact_processing_project_budget', 'processing_jobs', ['project_id', 'status', 'lease_until'], schema='artifacts')
    op.create_index('ix_artifact_processing_workspace_budget', 'processing_jobs', ['workspace_id', 'status', 'lease_until'], schema='artifacts')
    op.create_table('processing_attempts',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('job_id', sa.String(128), sa.ForeignKey('artifacts.processing_jobs.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('fencing_token', sa.BigInteger(), nullable=False), sa.Column('worker_id', sa.String(128), nullable=False),
        sa.Column('status', sa.String(32), nullable=False), sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('error_code', sa.String(128)),
        sa.UniqueConstraint('job_id', 'fencing_token', name='uq_artifact_processing_attempt_fence'), schema='artifacts')
    op.create_table('processing_outbox', *event_columns(),
        sa.Column('aggregate_id', postgresql.UUID(), nullable=False), sa.Column('metadata', postgresql.JSONB()),
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('idempotency_key', name='uq_artifact_processing_outbox_idempotency'), schema='artifacts')
    op.create_index('ix_artifact_processing_outbox_pending', 'processing_outbox', ['status', 'available_at', 'created_at'], schema='artifacts')
    op.create_table('processing_inbox', *event_columns(),
        sa.Column('message_id', sa.String(255), nullable=False), sa.Column('producer_module', sa.String(64), nullable=False),
        sa.Column('consumer_module', sa.String(64), nullable=False), sa.Column('outbox_origin_id', postgresql.UUID()),
        sa.Column('headers', postgresql.JSONB()), sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('consumer_name', sa.String(128)),
        sa.UniqueConstraint('message_id', 'consumer_module', name='uq_artifact_processing_inbox_message'),
        sa.UniqueConstraint('idempotency_key', name='uq_artifact_processing_inbox_idempotency'), schema='artifacts')

    op.create_index('ix_artifact_processing_inbox_job', 'processing_inbox', [sa.text("(payload ->> 'job_id')")], schema='artifacts')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.processing_jobs) OR EXISTS (SELECT 1 FROM artifacts.processing_outbox) OR EXISTS (SELECT 1 FROM artifacts.processing_inbox)')):
        raise RuntimeError('Durable processing requires a compatible reader')
    for table in ('processing_inbox', 'processing_outbox', 'processing_attempts', 'processing_jobs', 'processing_workspace_queue', 'processing_project_queue'):
        op.drop_table(table, schema='artifacts')
    op.drop_constraint('uq_artifact_workspace_scope_identity', 'workspaces', type_='unique', schema='artifacts')
