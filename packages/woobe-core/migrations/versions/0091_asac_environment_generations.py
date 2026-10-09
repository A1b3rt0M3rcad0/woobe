"""Monotonic native selections include legacy writes and detect A -> B -> A."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade():
    for owner, root in (("agent", "agents"), ("network", "networks")):
        op.create_table("asac_environment_selections",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("project_id", UUID(as_uuid=True), nullable=False),
            sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
            sa.Column("environment", sa.String(16), nullable=False),
            sa.Column("generation", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("snapshot_id", UUID(as_uuid=True), nullable=True),
            sa.Column("execution_fingerprint", sa.String(64), nullable=True),
            sa.UniqueConstraint("project_id", "resource_id", "environment", name=f"uq_{owner}_asac_environment_selection"),
            sa.CheckConstraint("generation >= 0", name=f"ck_{owner}_asac_environment_generation"),
            sa.CheckConstraint("environment IN ('staging', 'production')", name=f"ck_{owner}_asac_selection_environment"),
            sa.ForeignKeyConstraint(["resource_id"], [f"{owner}.{root}.id"], ondelete="CASCADE"), schema=owner)
        op.execute(f"""CREATE FUNCTION {owner}.guard_asac_environment_selection() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            IF EXISTS (SELECT 1 FROM {owner}.{root} WHERE id=OLD.resource_id) THEN
              RAISE EXCEPTION 'Environment selection history cannot be deleted';
            END IF;
            RETURN OLD;
          END IF;
          IF NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.resource_id IS DISTINCT FROM OLD.resource_id
             OR NEW.environment IS DISTINCT FROM OLD.environment OR NEW.id IS DISTINCT FROM OLD.id
             OR NEW.created_at IS DISTINCT FROM OLD.created_at
             OR NEW.generation != OLD.generation + 1
             OR (NEW.snapshot_id IS NOT DISTINCT FROM OLD.snapshot_id AND NEW.execution_fingerprint IS NOT DISTINCT FROM OLD.execution_fingerprint)
          THEN RAISE EXCEPTION 'Environment selection generation must advance with changed executable identity'; END IF;
          RETURN NEW;
        END $$""")
        op.execute(f"CREATE TRIGGER guard_asac_environment_selection BEFORE UPDATE OR DELETE ON {owner}.asac_environment_selections FOR EACH ROW EXECUTE FUNCTION {owner}.guard_asac_environment_selection()")

    # Always lock the native root before changing its selection. Deferred triggers
    # observe the final transaction state, not transient status demotion/promotion.
    op.execute("""CREATE FUNCTION agent.refresh_asac_environment_selection(p_resource uuid) RETURNS void LANGUAGE plpgsql AS $$
    DECLARE p_project uuid; p_env text; p_snapshot uuid; p_fingerprint text;
    BEGIN
      SELECT project_id INTO p_project FROM agent.agents WHERE id=p_resource FOR UPDATE;
      IF NOT FOUND THEN RETURN; END IF;
      FOREACH p_env IN ARRAY ARRAY['staging','production'] LOOP
        p_snapshot := NULL; p_fingerprint := NULL;
        SELECT id, encode(sha256(convert_to((to_jsonb(r) - ARRAY['status','updated_at','promoted_at','promoted_by'])::text,'UTF8')),'hex')
          INTO p_snapshot,p_fingerprint FROM agent.agent_releases r
          WHERE project_id=p_project AND agent_id=p_resource AND status=p_env
          ORDER BY updated_at DESC,id DESC LIMIT 1;
        INSERT INTO agent.asac_environment_selections(project_id,resource_id,environment,generation,snapshot_id,execution_fingerprint)
          VALUES(p_project,p_resource,p_env,CASE WHEN p_snapshot IS NULL THEN 0 ELSE 1 END,p_snapshot,p_fingerprint)
          ON CONFLICT(project_id,resource_id,environment) DO UPDATE SET
            generation=agent.asac_environment_selections.generation+1,
            snapshot_id=EXCLUDED.snapshot_id,execution_fingerprint=EXCLUDED.execution_fingerprint,updated_at=clock_timestamp()
          WHERE agent.asac_environment_selections.snapshot_id IS DISTINCT FROM EXCLUDED.snapshot_id
             OR agent.asac_environment_selections.execution_fingerprint IS DISTINCT FROM EXCLUDED.execution_fingerprint;
      END LOOP;
    END $$""")
    op.execute("""CREATE FUNCTION agent.observe_asac_environment_selection() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='agents' THEN PERFORM agent.refresh_asac_environment_selection(NEW.id);
      ELSE
        IF TG_OP!='INSERT' THEN PERFORM agent.refresh_asac_environment_selection(OLD.agent_id); END IF;
        IF TG_OP!='DELETE' THEN PERFORM agent.refresh_asac_environment_selection(NEW.agent_id); END IF;
      END IF;
      RETURN NULL;
    END $$""")
    op.execute("CREATE CONSTRAINT TRIGGER asac_agent_selection_change AFTER INSERT OR UPDATE OR DELETE ON agent.agent_releases DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION agent.observe_asac_environment_selection()")
    op.execute("CREATE CONSTRAINT TRIGGER asac_agent_selection_initialize AFTER INSERT ON agent.agents DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION agent.observe_asac_environment_selection()")
    op.execute("""CREATE FUNCTION network.refresh_asac_environment_selection(p_resource uuid) RETURNS void LANGUAGE plpgsql AS $$
    DECLARE p_project uuid; p_env text; p_snapshot uuid; p_fingerprint text;
    BEGIN
      SELECT project_id INTO p_project FROM network.networks WHERE id=p_resource FOR UPDATE;
      IF NOT FOUND THEN RETURN; END IF;
      FOREACH p_env IN ARRAY ARRAY['staging','production'] LOOP
        SELECT CASE WHEN p_env='staging' THEN staging_version_id ELSE production_version_id END INTO p_snapshot
          FROM network.networks WHERE id=p_resource;
        p_fingerprint := NULL;
        SELECT encode(sha256(convert_to((to_jsonb(r) - ARRAY['updated_at','activation_kind'])::text,'UTF8')),'hex') INTO p_fingerprint
          FROM network.network_versions r WHERE id=p_snapshot AND project_id=p_project AND network_id=p_resource;
        INSERT INTO network.asac_environment_selections(project_id,resource_id,environment,generation,snapshot_id,execution_fingerprint)
          VALUES(p_project,p_resource,p_env,CASE WHEN p_snapshot IS NULL THEN 0 ELSE 1 END,p_snapshot,p_fingerprint)
          ON CONFLICT(project_id,resource_id,environment) DO UPDATE SET
            generation=network.asac_environment_selections.generation+1,
            snapshot_id=EXCLUDED.snapshot_id,execution_fingerprint=EXCLUDED.execution_fingerprint,updated_at=clock_timestamp()
          WHERE network.asac_environment_selections.snapshot_id IS DISTINCT FROM EXCLUDED.snapshot_id
             OR network.asac_environment_selections.execution_fingerprint IS DISTINCT FROM EXCLUDED.execution_fingerprint;
      END LOOP;
    END $$""")
    op.execute("""CREATE FUNCTION network.observe_asac_environment_selection() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='networks' THEN
        IF TG_OP!='DELETE' THEN PERFORM network.refresh_asac_environment_selection(NEW.id); END IF;
      ELSE
        IF TG_OP!='INSERT' THEN PERFORM network.refresh_asac_environment_selection(OLD.network_id); END IF;
        IF TG_OP!='DELETE' THEN PERFORM network.refresh_asac_environment_selection(NEW.network_id); END IF;
      END IF;
      RETURN NULL;
    END $$""")
    op.execute("CREATE CONSTRAINT TRIGGER asac_network_selection_change AFTER INSERT OR UPDATE ON network.networks DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION network.observe_asac_environment_selection()")
    op.execute("CREATE CONSTRAINT TRIGGER asac_network_snapshot_change AFTER INSERT OR UPDATE OR DELETE ON network.network_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION network.observe_asac_environment_selection()")
    op.execute("SELECT agent.refresh_asac_environment_selection(id) FROM agent.agents")
    op.execute("SELECT network.refresh_asac_environment_selection(id) FROM network.networks")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM agent.asac_environment_selections WHERE generation>0)
      OR EXISTS(SELECT 1 FROM network.asac_environment_selections WHERE generation>0)
      THEN RAISE EXCEPTION 'Retained environment generations prevent destructive downgrade'; END IF;
    END $$""")
    for trigger, table, owner in (
        ("asac_agent_selection_change","agent_releases","agent"),
        ("asac_agent_selection_initialize","agents","agent"),
        ("asac_network_selection_change","networks","network"),
        ("asac_network_snapshot_change","network_versions","network"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {owner}.{table}")
    for owner in ("network","agent"):
        op.execute(f"DROP FUNCTION {owner}.observe_asac_environment_selection()")
        op.execute(f"DROP FUNCTION {owner}.refresh_asac_environment_selection(uuid)")
        op.drop_table("asac_environment_selections",schema=owner)
        op.execute(f"DROP FUNCTION {owner}.guard_asac_environment_selection()")
