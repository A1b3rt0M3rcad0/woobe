"""Capture explicit legacy Secret consumers without granting by name."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("project_configuration_legacy_consumers",
        sa.Column("alias_id", UUID(as_uuid=True), sa.ForeignKey("core.project_configuration_legacy_aliases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("consumer_kind", sa.String(32), primary_key=True),
        sa.Column("consumer_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("field_path", sa.String(512), primary_key=True), schema="core")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM core.project_configuration_legacy_consumers)")):
        raise RuntimeError("Retained legacy consumer authorizations prevent downgrade")
    op.drop_table("project_configuration_legacy_consumers", schema="core")
