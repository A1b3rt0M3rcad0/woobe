"""Check Project policy at deferred deployment commit as well as API composition."""
from alembic import op

revision='0097'
down_revision='0096'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""CREATE FUNCTION core.assert_asac_deployment_policy(project uuid, environment text, actor text, evidence jsonb)
      RETURNS void LANGUAGE plpgsql AS $$
      DECLARE policy core.asac_project_lifecycle_policies%ROWTYPE; expected jsonb;
      BEGIN
        PERFORM id FROM core.projects WHERE id=project FOR SHARE;
        SELECT * INTO policy FROM core.asac_project_lifecycle_policies WHERE project_id=project FOR SHARE;
        expected=evidence->'policy';
        IF expected IS NULL OR expected->>'generation' IS NULL OR expected->>'managed' IS NULL
          OR coalesce(policy.generation,0) IS DISTINCT FROM (expected->>'generation')::bigint
          OR coalesce(policy.managed,false) IS DISTINCT FROM (expected->>'managed')::boolean
        THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_STALE'; END IF;
        IF policy.managed AND environment='production' AND jsonb_array_length(policy.production_actors)>0
          AND NOT policy.production_actors ? actor
        THEN RAISE EXCEPTION 'ASAC_PROJECT_PRODUCTION_ACTOR_REQUIRED'; END IF;
      END $$""")
    for owner in ('agent','network'):
        op.execute(f"""CREATE FUNCTION {owner}.check_deployment_project_policy() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN
            PERFORM core.assert_asac_deployment_policy(NEW.project_id,NEW.environment,NEW.actor,NEW.evidence);
            RETURN NEW;
          END $$""")
        op.execute(f"CREATE CONSTRAINT TRIGGER deployment_project_policy AFTER INSERT ON {owner}.asac_deployments DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {owner}.check_deployment_project_policy()")


def downgrade():
    raise RuntimeError('Project policy must remain effective through deployment commit; use a forward migration')
