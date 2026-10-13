"""Retain Secret identity while centralizing active material."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE agent.provider_credentials SET authentication = NULL WHERE authentication = 'null'::jsonb")
    op.add_column("tool_secrets", sa.Column("configuration_reference", JSONB(), nullable=True), schema="agent")
    op.alter_column("tool_secrets", "encrypted_value", nullable=True, schema="agent")
    op.create_check_constraint("ck_secret_configuration_authority", "tool_secrets",
        "configuration_reference IS NULL OR encrypted_value IS NULL", schema="agent")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM agent.tool_secrets WHERE configuration_reference IS NOT NULL OR encrypted_value IS NULL)")):
        raise RuntimeError("Migrated Secret configuration requires a bridge reader")
    op.drop_constraint("ck_secret_configuration_authority", "tool_secrets", schema="agent")
    op.alter_column("tool_secrets", "encrypted_value", nullable=False, schema="agent")
    op.drop_column("tool_secrets", "configuration_reference", schema="agent")
