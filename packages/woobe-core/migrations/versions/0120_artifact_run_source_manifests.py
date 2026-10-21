"""Pin exact Artifact sources used by a Run."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "run_source_manifests",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("catalog_version", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "environment", "workspace_id"],
            ["artifacts.workspaces.project_id", "artifacts.workspaces.environment", "artifacts.workspaces.id"],
            name="fk_artifact_run_source_manifest_workspace", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("project_id", "environment", "workspace_id", "run_id",
                            name="uq_artifact_run_source_manifest"),
        sa.CheckConstraint("environment IN ('draft','staging','production')",
                           name="ck_artifact_run_source_manifest_environment"),
        sa.CheckConstraint("run_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'",
                           name="ck_artifact_run_source_manifest_run_id"),
        sa.CheckConstraint("catalog_version >= 0", name="ck_artifact_run_source_manifest_version"),
        schema="artifacts",
    )
    op.create_index("ix_artifact_run_source_manifest_run", "run_source_manifests",
                    ["workspace_id", "run_id"], schema="artifacts")
    op.create_table(
        "run_sources",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("manifest_id", sa.String(length=128), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["manifest_id"], ["artifacts.run_source_manifests.id"],
                                name="fk_artifact_run_source_manifest", ondelete="CASCADE"),
        sa.UniqueConstraint("manifest_id", "source_fingerprint", name="uq_artifact_run_source_fingerprint"),
        sa.CheckConstraint("source_fingerprint ~ '^[0-9a-f]{64}$'",
                           name="ck_artifact_run_source_fingerprint"),
        schema="artifacts",
    )
    op.create_index("ix_artifact_run_sources_manifest", "run_sources",
                    ["manifest_id", "id"], schema="artifacts")


def downgrade():
    op.drop_index("ix_artifact_run_sources_manifest", table_name="run_sources", schema="artifacts")
    op.drop_table("run_sources", schema="artifacts")
    op.drop_index("ix_artifact_run_source_manifest_run", table_name="run_source_manifests", schema="artifacts")
    op.drop_table("run_source_manifests", schema="artifacts")
