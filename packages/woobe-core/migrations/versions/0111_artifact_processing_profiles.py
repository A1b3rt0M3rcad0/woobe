"""Immutable scoped processing recipes and explicit Workspace defaults."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0111'
down_revision = '0110'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('processing_profiles',
        sa.Column('project_id', postgresql.UUID(), primary_key=True),
        sa.Column('environment', sa.String(16), primary_key=True),
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('revision', sa.BigInteger(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('recipe', postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("environment IN ('draft','staging','production')", name='ck_artifact_processing_profile_environment'),
        sa.CheckConstraint('revision >= 1', name='ck_artifact_processing_profile_revision'),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name='ck_artifact_processing_profile_fingerprint'), schema='artifacts')
    op.execute("""CREATE FUNCTION artifacts.reject_profile_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Artifact processing profile revisions are immutable'; END $$""")
    op.execute('CREATE TRIGGER artifact_profile_immutable BEFORE UPDATE ON artifacts.processing_profiles FOR EACH ROW EXECUTE FUNCTION artifacts.reject_profile_update()')
    op.add_column('workspaces', sa.Column('default_profile_id', sa.String(128)), schema='artifacts')
    op.add_column('workspaces', sa.Column('default_profile_revision', sa.BigInteger()), schema='artifacts')
    op.create_check_constraint('ck_artifact_workspace_profile_pair', 'workspaces',
        '(default_profile_id IS NULL) = (default_profile_revision IS NULL)', schema='artifacts')
    op.create_foreign_key('fk_artifact_workspace_profile', 'workspaces', 'processing_profiles',
        ['project_id', 'environment', 'default_profile_id', 'default_profile_revision'],
        ['project_id', 'environment', 'id', 'revision'], source_schema='artifacts', referent_schema='artifacts')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.processing_profiles)')):
        raise RuntimeError('Processing recipe snapshots require a compatible reader')
    op.drop_constraint('fk_artifact_workspace_profile', 'workspaces', type_='foreignkey', schema='artifacts')
    op.drop_constraint('ck_artifact_workspace_profile_pair', 'workspaces', type_='check', schema='artifacts')
    op.drop_column('workspaces', 'default_profile_revision', schema='artifacts')
    op.drop_column('workspaces', 'default_profile_id', schema='artifacts')
    op.drop_table('processing_profiles', schema='artifacts')
    op.execute('DROP FUNCTION artifacts.reject_profile_update()')
