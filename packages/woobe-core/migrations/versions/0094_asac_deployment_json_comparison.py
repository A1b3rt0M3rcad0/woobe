"""Compare original operation JSON to deployment outbox JSONB without rewriting history."""
from alembic import op
import sqlalchemy as sa

revision='0094'
down_revision='0093'
branch_labels=None
depends_on=None


def upgrade():
    for owner in ('agent','network'):
        definition=op.get_bind().execute(sa.text('SELECT pg_get_functiondef(CAST(:name AS regprocedure))'),
            {'name':f'{owner}.check_asac_deployment_commit()'}).scalar_one()
        original='event.payload IS DISTINCT FROM operation.result'
        if definition.count(original)!=1:
            raise RuntimeError('Unexpected deployment proof function; refusing ambiguous amendment')
        op.execute(definition.replace(original,'event.payload IS DISTINCT FROM operation.result::jsonb'))


def downgrade():
    raise RuntimeError('Reverting would disable the deployment commit proof; use a forward migration')
