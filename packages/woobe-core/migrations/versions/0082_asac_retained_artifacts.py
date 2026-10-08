"""Retain verified closed artifacts independently of private upload lifetimes."""
from alembic import op
import sqlalchemy as sa

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("snapshot_artifacts",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("definition_digest", sa.String(71), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("inventory", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("component_digests", sa.JSON(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.UniqueConstraint("project_id", "artifact_digest", name="uq_package_snapshot_artifact"), schema="package")


def downgrade():
    op.drop_table("snapshot_artifacts", schema="package")
