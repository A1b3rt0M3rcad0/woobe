"""Recoverable owner phases and immutable exact Network publications."""
from alembic import op
import sqlalchemy as sa

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def _base():
    return [sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def _uuids(names):
    return [sa.Column(name, sa.UUID(), nullable=False) for name in names]


def _immutable(schema, table):
    function = "guard_" + table
    op.execute(f"""CREATE FUNCTION {schema}.{function}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Immutable ASaC evidence cannot be modified or deleted'; END $$""")
    op.execute(f"CREATE TRIGGER {function} BEFORE UPDATE OR DELETE ON {schema}.{table} FOR EACH ROW EXECUTE FUNCTION {schema}.{function}()")


def upgrade():
    op.create_table("asac_publications", *_base(), *_uuids([
        "project_id", "resource_id", "resource_uid", "candidate_id", "evaluation_id", "release_id", "operation_id"]),
        sa.Column("release_version", sa.String(64), nullable=False), sa.Column("revision_id", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(96), nullable=False), sa.Column("request_digest", sa.String(71), nullable=False),
        sa.Column("reused", sa.Boolean(), nullable=False), sa.Column("reason", sa.String(2048), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name="uq_network_asac_publication_operation"),
        sa.ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["network.asac_candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["network.asac_evaluations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["release_id"], ["network.network_versions.id"], ondelete="RESTRICT"), schema="network")
    op.create_table("asac_publication_preparations", *_base(), *_uuids([
        "project_id", "resource_id", "resource_uid", "candidate_id", "evaluation_id", "operation_id"]),
        sa.Column("actor", sa.String(96), nullable=False), sa.Column("request_digest", sa.String(71), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False), sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("children", sa.JSON(), nullable=False), sa.Column("state", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("cancel_reason", sa.String(2048), nullable=True),
        sa.UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name="uq_network_asac_publication_preparation_operation"),
        sa.CheckConstraint("state IN ('preparing', 'published', 'cancelled')", name="ck_network_asac_publication_preparation_state"),
        sa.ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["network.asac_candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["network.asac_evaluations.id"], ondelete="RESTRICT"), schema="network")
    op.create_table("asac_constituent_publications", *_base(), *_uuids([
        "project_id", "resource_id", "publication_id", "node_id", "agent_id", "source_snapshot_id", "release_id"]),
        sa.Column("runtime_digest", sa.String(71), nullable=False),
        sa.UniqueConstraint("publication_id", "node_id", name="uq_network_asac_constituent_publication_node"),
        sa.ForeignKeyConstraint(["publication_id"], ["network.asac_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["agent.agent_releases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["release_id"], ["agent.agent_releases.id"], ondelete="RESTRICT"), schema="network")
    _immutable("network", "asac_publications")
    _immutable("network", "asac_constituent_publications")
    for owner in ("agent", "network"):
        _immutable(owner, "asac_operations")
    op.execute("""CREATE FUNCTION network.guard_asac_publication_preparation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' OR (OLD.state IN ('published','cancelled') AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)) THEN
            RAISE EXCEPTION 'Accepted ASaC publication cannot be modified or deleted'; END IF;
        IF (to_jsonb(NEW) - ARRAY['children','state','error_code','cancel_reason','updated_at'])
            IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['children','state','error_code','cancel_reason','updated_at']) THEN
            RAISE EXCEPTION 'Original ASaC publication preparation identity is immutable'; END IF;
        IF EXISTS (SELECT 1 FROM jsonb_each(OLD.children::jsonb) previous
            WHERE NEW.children::jsonb -> previous.key IS DISTINCT FROM previous.value) THEN
            RAISE EXCEPTION 'Original ASaC constituent phase receipt is immutable'; END IF;
        RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER guard_asac_publication_preparation BEFORE UPDATE OR DELETE ON network.asac_publication_preparations
        FOR EACH ROW EXECUTE FUNCTION network.guard_asac_publication_preparation()""")
    op.execute("""CREATE INDEX ix_agent_asac_constituent_release ON agent.asac_operations
        ((result::jsonb ->> 'release_id')) WHERE result::jsonb ? 'parent_operation_id'""")
    op.execute("""CREATE FUNCTION agent.guard_asac_published_native_release() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF EXISTS (SELECT 1 FROM agent.asac_publications WHERE release_id = OLD.id)
        OR EXISTS (SELECT 1 FROM agent.asac_operations WHERE result::jsonb ? 'parent_operation_id'
            AND result::jsonb ->> 'release_id' = OLD.id::text) THEN
            IF TG_OP = 'DELETE' OR (to_jsonb(NEW) - ARRAY['status','promoted_by','promoted_at','updated_at'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','promoted_by','promoted_at','updated_at']) THEN
                RAISE EXCEPTION 'Published ASaC Agent executable content is immutable'; END IF;
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER guard_asac_published_native_release BEFORE UPDATE OR DELETE ON agent.agent_releases
        FOR EACH ROW EXECUTE FUNCTION agent.guard_asac_published_native_release()""")
    op.execute("""CREATE FUNCTION network.guard_asac_published_native_release() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF EXISTS (SELECT 1 FROM network.asac_publications WHERE release_id = OLD.id) THEN
            IF TG_OP = 'DELETE' OR (to_jsonb(NEW) - 'updated_at') IS DISTINCT FROM (to_jsonb(OLD) - 'updated_at') THEN
                RAISE EXCEPTION 'Published ASaC Network executable content is immutable'; END IF;
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER guard_asac_published_native_release BEFORE UPDATE OR DELETE ON network.network_versions
        FOR EACH ROW EXECUTE FUNCTION network.guard_asac_published_native_release()""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM network.asac_publication_preparations)
        OR EXISTS (SELECT 1 FROM network.asac_publications)
        OR EXISTS (SELECT 1 FROM agent.asac_publications)
        OR EXISTS (SELECT 1 FROM agent.asac_operations WHERE result::jsonb ? 'parent_operation_id')
        THEN RAISE EXCEPTION 'Retained Network publication prevents destructive downgrade'; END IF; END $$""")
    for owner, table in (("network", "network_versions"), ("agent", "agent_releases")):
        op.execute(f"DROP TRIGGER guard_asac_published_native_release ON {owner}.{table}")
        op.execute(f"DROP FUNCTION {owner}.guard_asac_published_native_release()")
    op.execute("DROP INDEX agent.ix_agent_asac_constituent_release")
    op.execute("DROP TRIGGER guard_asac_publication_preparation ON network.asac_publication_preparations")
    op.execute("DROP FUNCTION network.guard_asac_publication_preparation()")
    for owner, table in (("agent", "asac_operations"), ("network", "asac_operations"),
        ("network", "asac_constituent_publications"), ("network", "asac_publications")):
        op.execute(f"DROP TRIGGER guard_{table} ON {owner}.{table}")
        op.execute(f"DROP FUNCTION {owner}.guard_{table}()")
    for table in ("asac_constituent_publications", "asac_publication_preparations", "asac_publications"):
        op.drop_table(table, schema="network")
