"""Retain exact author source independently of upload actor and expiry."""
from alembic import op
import sqlalchemy as sa

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("author_artifacts",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("actor", sa.String(96), nullable=False),
        sa.Column("author_digest", sa.String(71), nullable=False),
        sa.Column("resource_uid", sa.UUID(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("transport_digest", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), schema="package")
    for owner in ("agent", "network"):
        op.add_column("asac_revisions", sa.Column("author_artifact_id", sa.UUID(), nullable=True), schema=owner)


def downgrade():
    for owner in ("agent", "network"):
        op.drop_column("asac_revisions", "author_artifact_id", schema=owner)
    op.drop_table("author_artifacts", schema="package")
