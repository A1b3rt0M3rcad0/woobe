"""Exact Agent publications retain qualified Candidate provenance separately."""
from alembic import op
import sqlalchemy as sa

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("asac_publications",
        sa.Column("id",sa.UUID(),primary_key=True,nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        *[sa.Column(name,sa.UUID(),nullable=False) for name in (
            "project_id","resource_id","resource_uid","candidate_id","evaluation_id","release_id","operation_id")],
        sa.Column("release_version",sa.String(64),nullable=False),
        sa.Column("revision_id",sa.String(40),nullable=False),
        sa.Column("actor",sa.String(96),nullable=False),
        sa.Column("request_digest",sa.String(71),nullable=False),
        sa.Column("reused",sa.Boolean(),nullable=False),
        sa.Column("reason",sa.String(2048),nullable=False),
        sa.Column("evidence",sa.JSON(),nullable=False),
        sa.UniqueConstraint("project_id","resource_id","actor","operation_id",name="uq_agent_asac_publication_operation"),
        sa.ForeignKeyConstraint(["resource_id"],["agent.agents.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"],["agent.asac_candidates.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluation_id"],["agent.asac_evaluations.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["release_id"],["agent.agent_releases.id"],ondelete="RESTRICT"),schema="agent")
    op.execute("""CREATE FUNCTION agent.guard_asac_publication() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'Immutable ASaC publication receipt cannot be modified or deleted'; END $$""")
    op.execute("""CREATE TRIGGER guard_asac_publication BEFORE UPDATE OR DELETE ON agent.asac_publications
        FOR EACH ROW EXECUTE FUNCTION agent.guard_asac_publication()""")
    for owner in ("agent","network"):
        op.execute(f"""CREATE FUNCTION {owner}.guard_asac_ready_candidate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP = 'DELETE' OR (OLD.state IN ('ready','rejected') AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)) THEN
                RAISE EXCEPTION 'Sealed ASaC Candidate evidence cannot be modified or deleted';
            END IF;
            IF (to_jsonb(NEW) - ARRAY['state','root_snapshot_id','runtime_digest','native_bindings','runtime_fingerprints','updated_at'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['state','root_snapshot_id','runtime_digest','native_bindings','runtime_fingerprints','updated_at']) THEN
                RAISE EXCEPTION 'Accepted ASaC Candidate identity is immutable';
            END IF;
            RETURN NEW;
        END $$""")
        op.execute(f"""CREATE TRIGGER guard_asac_ready_candidate BEFORE UPDATE OR DELETE ON {owner}.asac_candidates
            FOR EACH ROW EXECUTE FUNCTION {owner}.guard_asac_ready_candidate()""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM agent.asac_publications)
        THEN RAISE EXCEPTION 'Retained publication evidence prevents destructive downgrade'; END IF; END $$""")
    for owner in ("network","agent"):
        op.execute(f"DROP TRIGGER guard_asac_ready_candidate ON {owner}.asac_candidates")
        op.execute(f"DROP FUNCTION {owner}.guard_asac_ready_candidate()")
    op.execute("DROP TRIGGER guard_asac_publication ON agent.asac_publications")
    op.execute("DROP FUNCTION agent.guard_asac_publication()")
    op.drop_table("asac_publications",schema="agent")
