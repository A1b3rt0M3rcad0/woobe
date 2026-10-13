"""Separate preparation authorization from immutable vector build intent."""
from alembic import op
import sqlalchemy as sa

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vector_snapshots", sa.Column("preparation_environment", sa.String(16), nullable=True), schema="agent")
    op.create_check_constraint("ck_vector_preparation_environment", "vector_snapshots",
        "preparation_environment IS NULL OR preparation_environment IN ('draft', 'staging', 'production')", schema="agent")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM agent.vector_snapshots WHERE preparation_environment IS NOT NULL)")):
        raise RuntimeError("Retained vector preparation authorizations prevent downgrade")
    op.drop_constraint("ck_vector_preparation_environment", "vector_snapshots", schema="agent")
    op.drop_column("vector_snapshots", "preparation_environment", schema="agent")
