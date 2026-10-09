"""Detached owner candidates and retained exact revision component identities."""
from alembic import op
import sqlalchemy as sa

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_agent_releases_snapshot_kind", "agent_releases", schema="agent", type_="check")
    op.create_check_constraint("ck_agent_releases_snapshot_kind", "agent_releases", "snapshot_kind IN ('draft', 'staging', 'release', 'candidate')", schema="agent")
    for owner, root, snapshots in (("agent", "agents", "agent_releases"), ("network", "networks", "network_versions")):
        op.add_column("asac_revisions", sa.Column("component_uids", sa.JSON(), nullable=True), schema=owner)
        op.add_column("asac_revisions", sa.Column("provider_uids", sa.JSON(), nullable=True), schema=owner)
        op.create_table("asac_candidates",
            sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("project_id", sa.UUID(), nullable=False),
            sa.Column("resource_id", sa.UUID(), nullable=False),
            sa.Column("resource_uid", sa.UUID(), nullable=False),
            sa.Column("actor", sa.String(96), nullable=False),
            sa.Column("operation_id", sa.UUID(), nullable=False),
            sa.Column("request_digest", sa.String(71), nullable=False),
            sa.Column("revision_id", sa.String(39), nullable=False),
            sa.Column("record_digest", sa.String(71), nullable=False),
            sa.Column("artifact_id", sa.UUID(), nullable=False),
            sa.Column("draft_id", sa.UUID(), nullable=False),
            sa.Column("draft_generation", sa.Integer(), nullable=False),
            sa.Column("preparation_operation_id", sa.UUID(), nullable=False),
            sa.Column("state", sa.String(16), nullable=False),
            sa.Column("root_snapshot_id", sa.UUID(), nullable=True),
            sa.Column("snapshot_ids", sa.JSON(), nullable=False),
            sa.Column("native_bindings", sa.JSON(), nullable=False),
            sa.Column("runtime_digest", sa.String(71), nullable=True),
            sa.Column("runtime_fingerprints", sa.JSON(), nullable=False),
            sa.UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name=f"uq_{owner}_asac_candidate_operation"),
            sa.CheckConstraint("draft_generation >= 1", name=f"ck_{owner}_asac_candidate_generation"),
            sa.CheckConstraint("state IN ('preparing', 'ready', 'rejected')", name=f"ck_{owner}_asac_candidate_state"),
            sa.ForeignKeyConstraint(["resource_id"], [f"{owner}.{root}.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["draft_id"], [f"{owner}.asac_drafts.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["project_id", "resource_uid", "revision_id"], [f"{owner}.asac_revisions.project_id", f"{owner}.asac_revisions.resource_uid", f"{owner}.asac_revisions.revision_id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["root_snapshot_id"], [f"{owner}.{snapshots}.id"], ondelete="RESTRICT"), schema=owner)
    for owner, table, field in (("agent", "agent_releases", "snapshot_kind"), ("network", "network_versions", "kind")):
        op.execute(f"""CREATE FUNCTION {owner}.guard_asac_candidate_snapshot() RETURNS trigger AS $$
            BEGIN
                IF OLD.{field} = 'candidate' THEN
                    RAISE EXCEPTION 'ASAC_CANDIDATE_IMMUTABLE: candidate snapshots cannot be changed or deleted';
                END IF;
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql""")
        op.execute(f"CREATE TRIGGER guard_asac_candidate_snapshot BEFORE UPDATE OR DELETE ON {owner}.{table} FOR EACH ROW EXECUTE FUNCTION {owner}.guard_asac_candidate_snapshot()")


def downgrade():
    # Do not silently discard candidate history or reinterpret it as a Release.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM agent.asac_candidates)
        OR EXISTS (SELECT 1 FROM network.asac_candidates)
        OR EXISTS (SELECT 1 FROM agent.agent_releases WHERE snapshot_kind = 'candidate')
        OR EXISTS (SELECT 1 FROM network.network_versions WHERE kind = 'candidate')
        THEN RAISE EXCEPTION 'Retained ASaC candidates prevent destructive downgrade';
        END IF; END $$""")
    for owner, table in (("network", "network_versions"), ("agent", "agent_releases")):
        op.execute(f"DROP TRIGGER guard_asac_candidate_snapshot ON {owner}.{table}")
        op.execute(f"DROP FUNCTION {owner}.guard_asac_candidate_snapshot()")
    for owner in ("network", "agent"):
        op.drop_table("asac_candidates", schema=owner)
        op.drop_column("asac_revisions", "provider_uids", schema=owner)
        op.drop_column("asac_revisions", "component_uids", schema=owner)
    op.drop_constraint("ck_agent_releases_snapshot_kind", "agent_releases", schema="agent", type_="check")
    op.create_check_constraint("ck_agent_releases_snapshot_kind", "agent_releases", "snapshot_kind IN ('draft', 'staging', 'release')", schema="agent")
