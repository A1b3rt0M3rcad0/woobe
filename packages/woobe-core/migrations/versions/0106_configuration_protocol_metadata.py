"""Version public credential lifetime metadata with its central material."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0106'
down_revision = '0105'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('project_environment_values', 'project_configuration_legacy_values', 'project_configuration_value_versions'):
        op.add_column(table, sa.Column('protocol_metadata', JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb")), schema='core')


def downgrade():
    # A pre-metadata bridge could mistake an expired token for an indefinite
    # one. Do not silently discard material interpretation during rollback.
    for table in ('project_environment_values', 'project_configuration_legacy_values', 'project_configuration_value_versions'):
        if op.get_bind().scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM core.{table} WHERE protocol_metadata <> '{{}}'::jsonb)")):
            raise RuntimeError('Credential protocol metadata requires a compatible bridge reader')
    for table in ('project_configuration_value_versions', 'project_configuration_legacy_values', 'project_environment_values'):
        op.drop_column(table, 'protocol_metadata', schema='core')
