"""Add portable package artifacts and transaction-bound import receipts.

Revision ID: 0078
Revises: 0077
"""

import sqlalchemy as sa
from alembic import op

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def _base_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def _identity_columns():
    return [
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(96), nullable=False),
    ]


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS package")
    op.create_table(
        "uploads",
        *_base_columns(),
        *_identity_columns(),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("inventory", sa.JSON(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="package",
    )
    op.create_index(
        "ix_package_upload_expiry", "uploads", ["expires_at"], schema="package"
    )
    op.create_table(
        "plans",
        *_base_columns(),
        *_identity_columns(),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("plan_digest", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="package",
    )
    op.create_index("ix_package_plan_expiry", "plans", ["expires_at"], schema="package")
    op.create_table(
        "operations",
        *_base_columns(),
        *_identity_columns(),
        sa.Column("key_digest", sa.LargeBinary(), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("principal_ciphertext", sa.Text(), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle", sa.String(16), nullable=False),
        sa.Column("lifecycle_state", sa.String(16), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("phase", sa.String(160), nullable=True),
        sa.Column("phases_completed", sa.Integer(), nullable=False),
        sa.Column("phases_total", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration_ready", sa.Boolean(), nullable=False),
        sa.Column("execution_ready", sa.Boolean(), nullable=False),
        sa.Column("inventory", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "project_id", "actor", "key_digest", name="uq_package_operation_identity"
        ),
        schema="package",
    )
    op.create_index(
        "ix_package_operation_claim",
        "operations",
        ["state", "lease_until"],
        schema="package",
    )
    op.create_table(
        "effects",
        *_base_columns(),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(160), nullable=False),
        sa.Column("response_ciphertext", sa.Text(), nullable=False),
        sa.UniqueConstraint("operation_id", "phase", name="uq_package_effect_phase"),
        schema="package",
    )
    op.create_table(
        "exports",
        *_base_columns(),
        *_identity_columns(),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("transport_digest", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("inventory", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="package",
    )
    op.create_index(
        "ix_package_export_expiry", "exports", ["expires_at"], schema="package"
    )


def downgrade():
    for table in ("exports", "effects", "operations", "plans", "uploads"):
        op.drop_table(table, schema="package")
    op.execute("DROP SCHEMA package")
