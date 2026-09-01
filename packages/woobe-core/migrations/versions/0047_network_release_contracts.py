"""Add Network release contracts and structured runtime outputs.

Revision ID: 0047
Revises: 0046
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    for name, column in (
        ("source_draft_revision", sa.Column("source_draft_revision", sa.Integer(), nullable=True)),
        ("source_staging_version_id", sa.Column("source_staging_version_id", UUID, nullable=True)),
        ("entry_agent_id", sa.Column("entry_agent_id", UUID, nullable=True)),
        ("entry_agent_release_id", sa.Column("entry_agent_release_id", UUID, nullable=True)),
        ("entry_agent_release_version", sa.Column("entry_agent_release_version", sa.String(64), nullable=True)),
        ("public_output_contract", sa.Column("public_output_contract", JSONB, nullable=True)),
        ("public_output_contract_hash", sa.Column("public_output_contract_hash", sa.String(64), nullable=True)),
        ("agent_release_manifest", sa.Column("agent_release_manifest", JSONB, nullable=True)),
        ("agent_release_manifest_hash", sa.Column("agent_release_manifest_hash", sa.String(64), nullable=True)),
        ("runtime_settings_hash", sa.Column("runtime_settings_hash", sa.String(64), nullable=True)),
        ("release_fingerprint", sa.Column("release_fingerprint", sa.String(64), nullable=True)),
        ("change_kind", sa.Column("change_kind", sa.String(32), nullable=True)),
    ):
        op.add_column("network_versions", column, schema="network")

    op.create_foreign_key(
        "fk_network_versions_source_staging_version",
        "network_versions",
        "network_versions",
        ["source_staging_version_id"],
        ["id"],
        source_schema="network",
        referent_schema="network",
    )
    op.create_foreign_key(
        "fk_network_versions_entry_agent_release",
        "network_versions",
        "agent_releases",
        ["entry_agent_release_id"],
        ["id"],
        source_schema="network",
        referent_schema="agent",
    )
    op.create_check_constraint(
        "ck_network_versions_change_kind",
        "network_versions",
        "change_kind IS NULL OR change_kind IN ('compatibility', 'feature', 'change')",
        schema="network",
    )
    op.create_index(
        "ix_network_versions_release_fingerprint",
        "network_versions",
        ["network_id", "release_fingerprint"],
        schema="network",
    )

    op.add_column("network_executions", sa.Column("parsed_output", JSONB, nullable=True), schema="network")
    op.add_column("network_executions", sa.Column("output_parse_error", sa.Text(), nullable=True), schema="network")
    op.add_column("network_invocations", sa.Column("parsed_output", JSONB, nullable=True), schema="network")
    op.add_column("network_invocations", sa.Column("output_parse_error", sa.Text(), nullable=True), schema="network")

    op.create_table(
        "network_production_activations",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("network_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("version_id", UUID, nullable=False),
        sa.Column("previous_version_id", UUID, nullable=True),
        sa.Column("activation_kind", sa.String(32), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=False),
        sa.Column("created_by", UUID, nullable=True),
        sa.ForeignKeyConstraint(["network_id"], ["network.networks.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["network.network_versions.id"]),
        sa.ForeignKeyConstraint(["previous_version_id"], ["network.network_versions.id"]),
        sa.CheckConstraint("activation_kind IN ('publish', 'reactivate', 'rollback')", name="ck_network_production_activations_kind"),
        schema="network",
    )
    op.create_index(
        "ix_network_production_activations_network_created",
        "network_production_activations",
        ["network_id", "created_at"],
        schema="network",
    )


def downgrade() -> None:
    op.drop_index("ix_network_production_activations_network_created", table_name="network_production_activations", schema="network")
    op.drop_table("network_production_activations", schema="network")
    op.drop_column("network_invocations", "output_parse_error", schema="network")
    op.drop_column("network_invocations", "parsed_output", schema="network")
    op.drop_column("network_executions", "output_parse_error", schema="network")
    op.drop_column("network_executions", "parsed_output", schema="network")
    op.drop_index("ix_network_versions_release_fingerprint", table_name="network_versions", schema="network")
    op.drop_constraint("ck_network_versions_change_kind", "network_versions", schema="network", type_="check")
    op.drop_constraint("fk_network_versions_entry_agent_release", "network_versions", schema="network", type_="foreignkey")
    op.drop_constraint("fk_network_versions_source_staging_version", "network_versions", schema="network", type_="foreignkey")
    for name in (
        "change_kind",
        "release_fingerprint",
        "runtime_settings_hash",
        "agent_release_manifest_hash",
        "agent_release_manifest",
        "public_output_contract_hash",
        "public_output_contract",
        "entry_agent_release_version",
        "entry_agent_release_id",
        "entry_agent_id",
        "source_staging_version_id",
        "source_draft_revision",
    ):
        op.drop_column("network_versions", name, schema="network")
