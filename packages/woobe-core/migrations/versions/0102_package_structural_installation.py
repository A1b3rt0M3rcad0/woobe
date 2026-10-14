"""Persist explicitly negotiated structural installation identity."""
from alembic import op
import sqlalchemy as sa

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("operations", sa.Column("package_schema_version", sa.String(8), nullable=False, server_default="1.0"), schema="package")
    op.add_column("operations", sa.Column("installation_mode", sa.String(16), nullable=False, server_default="operational"), schema="package")


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM package.operations WHERE package_schema_version <> '1.0' OR installation_mode <> 'operational')")):
        raise RuntimeError("Retained structural operation identities prevent downgrade")
    op.drop_column("operations", "installation_mode", schema="package")
    op.drop_column("operations", "package_schema_version", schema="package")
