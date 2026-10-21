"""Persist external Tool output provenance and operation references."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "revisions",
        sa.Column("external_operation_ref", sa.String(length=512), nullable=True),
        schema="artifacts",
    )
    op.add_column(
        "revisions",
        sa.Column(
            "source_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="artifacts",
    )
    op.add_column(
        "uploads",
        sa.Column("producer_id", sa.String(length=128), nullable=True),
        schema="artifacts",
    )
    op.add_column(
        "uploads",
        sa.Column("external_operation_ref", sa.String(length=512), nullable=True),
        schema="artifacts",
    )
    op.add_column(
        "uploads",
        sa.Column(
            "source_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="artifacts",
    )
    op.create_check_constraint(
        "ck_artifact_revision_external_operation_ref",
        "revisions",
        "external_operation_ref IS NULL OR (length(external_operation_ref) BETWEEN 1 AND 512 AND external_operation_ref !~ '[[:cntrl:]]')",
        schema="artifacts",
    )
    op.create_check_constraint(
        "ck_artifact_upload_external_operation_ref",
        "uploads",
        "external_operation_ref IS NULL OR (length(external_operation_ref) BETWEEN 1 AND 512 AND external_operation_ref !~ '[[:cntrl:]]')",
        schema="artifacts",
    )


def downgrade():
    op.drop_constraint("ck_artifact_upload_external_operation_ref", "uploads", schema="artifacts")
    op.drop_constraint("ck_artifact_revision_external_operation_ref", "revisions", schema="artifacts")
    for table, column in (
        ("uploads", "source_refs"),
        ("uploads", "external_operation_ref"),
        ("uploads", "producer_id"),
        ("revisions", "source_refs"),
        ("revisions", "external_operation_ref"),
    ):
        op.drop_column(table, column, schema="artifacts")
