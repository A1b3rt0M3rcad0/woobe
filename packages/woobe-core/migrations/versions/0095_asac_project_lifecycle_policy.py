"""Project-owned lifecycle policy, audit and legacy publication/selection gates."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision='0095'
down_revision='0094'
branch_labels=None
depends_on=None


def _base():
    return [sa.Column('id',sa.UUID(),primary_key=True,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]


def upgrade():
    op.create_table('asac_project_lifecycle_policies',*_base(),
        sa.Column('project_id',sa.UUID(),nullable=False),sa.Column('generation',sa.BigInteger(),nullable=False),
        sa.Column('managed',sa.Boolean(),nullable=False),sa.Column('production_actors',JSONB(),nullable=False),
        sa.ForeignKeyConstraint(['project_id'],['core.projects.id'],ondelete='RESTRICT'),
        sa.UniqueConstraint('project_id',name='uq_core_asac_policy_project'),
        sa.CheckConstraint('generation >= 1',name='ck_core_asac_policy_generation'),schema='core')
    op.create_table('asac_project_lifecycle_operations',*_base(),
        sa.Column('project_id',sa.UUID(),nullable=False),sa.Column('operation_id',sa.UUID(),nullable=False),
        sa.Column('actor',sa.String(128),nullable=False),sa.Column('request_digest',sa.String(71),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),sa.Column('result',JSONB(),nullable=False),
        sa.Column('outbox_id',sa.UUID(),nullable=False),
        sa.ForeignKeyConstraint(['project_id'],['core.projects.id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['outbox_id'],['core.outbox_events.id'],deferrable=True,initially='DEFERRED'),
        sa.UniqueConstraint('operation_id',name='uq_core_asac_policy_operation'),schema='core')
    op.execute("""CREATE FUNCTION core.asac_project_is_managed(project uuid) RETURNS boolean LANGUAGE plpgsql AS $$
      BEGIN
        PERFORM id FROM core.projects WHERE id=project FOR SHARE;
        RETURN coalesce((SELECT managed FROM core.asac_project_lifecycle_policies WHERE project_id=project),false);
      END $$""")
    op.execute("""CREATE FUNCTION core.guard_asac_policy_identity() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_IMMUTABLE'; END IF;
        IF TG_OP='INSERT' AND NEW.generation<>1 THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_STALE'; END IF;
        IF TG_OP='UPDATE' AND (NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.id IS DISTINCT FROM OLD.id
          OR NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.generation<>OLD.generation+1)
        THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_STALE'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("CREATE TRIGGER asac_policy_identity BEFORE INSERT OR UPDATE OR DELETE ON core.asac_project_lifecycle_policies FOR EACH ROW EXECUTE FUNCTION core.guard_asac_policy_identity()")
    op.execute("""CREATE FUNCTION core.check_asac_policy_commit() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE receipt core.asac_project_lifecycle_operations%ROWTYPE; event core.outbox_events%ROWTYPE;
      BEGIN
        SELECT * INTO receipt FROM core.asac_project_lifecycle_operations
          WHERE operation_id=nullif(current_setting('woobe.asac_policy_operation',true),'')::uuid AND project_id=NEW.project_id;
        SELECT * INTO event FROM core.outbox_events WHERE id=receipt.outbox_id;
        IF receipt.id IS NULL OR event.id IS NULL OR event.payload IS DISTINCT FROM receipt.result
          OR event.aggregate_id IS DISTINCT FROM NEW.project_id OR event.event_type<>'project.asac.lifecycle-policy.changed'
          OR receipt.result->'policy' IS DISTINCT FROM jsonb_build_object('project_id',NEW.project_id::text,
            'schema_version','1.0','generation',NEW.generation,'managed',NEW.managed,'production_actors',NEW.production_actors)
          OR (receipt.result->'before'->>'generation')::bigint<>NEW.generation-1
        THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_RECEIPT_REQUIRED'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("CREATE CONSTRAINT TRIGGER asac_policy_commit AFTER INSERT OR UPDATE ON core.asac_project_lifecycle_policies DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION core.check_asac_policy_commit()")
    op.execute("""CREATE FUNCTION core.guard_asac_policy_operation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_IMMUTABLE'; END $$""")
    op.execute("CREATE TRIGGER asac_policy_operation_immutable BEFORE UPDATE OR DELETE ON core.asac_project_lifecycle_operations FOR EACH ROW EXECUTE FUNCTION core.guard_asac_policy_operation()")
    for owner,table,root in [('agent','agent_releases','agent_id'),('network','network_versions','network_id')]:
        forbidden="NEW.status IN ('staging','production')" if owner=='agent' else "NEW.kind='staging'"
        released="NEW.snapshot_kind='release'" if owner=='agent' else "NEW.kind='release'"
        constituent="""OR EXISTS(SELECT 1 FROM agent.asac_operations o WHERE o.project_id=NEW.project_id
            AND o.resource_id=NEW.agent_id AND o.result::jsonb->>'release_id'=NEW.id::text
            AND o.result::jsonb ? 'parent_candidate_id' AND o.result::jsonb ? 'parent_evaluation_id'
            AND o.result::jsonb->>'write_outcome'='committed')""" if owner=='agent' else ''
        op.execute(f"""CREATE FUNCTION {owner}.check_managed_asac_release() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN
            IF NOT core.asac_project_is_managed(NEW.project_id) THEN RETURN NEW; END IF;
            IF {forbidden} THEN RAISE EXCEPTION 'ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED'; END IF;
            IF TG_OP='INSERT' AND {released} AND NOT (
              EXISTS(SELECT 1 FROM {owner}.asac_publications p WHERE p.project_id=NEW.project_id
                AND p.resource_id=NEW.{root} AND p.release_id=NEW.id) {constituent})
            THEN RAISE EXCEPTION 'ASAC_PROJECT_QUALIFIED_PUBLICATION_REQUIRED'; END IF;
            RETURN NEW;
          END $$""")
        op.execute(f"CREATE CONSTRAINT TRIGGER managed_asac_release AFTER INSERT OR UPDATE ON {owner}.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {owner}.check_managed_asac_release()")
    op.execute("""CREATE FUNCTION network.check_managed_asac_pointer() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF core.asac_project_is_managed(NEW.project_id) AND
          ((TG_OP='INSERT' AND (NEW.staging_version_id IS NOT NULL OR NEW.production_version_id IS NOT NULL)) OR
           (TG_OP='UPDATE' AND (NEW.staging_version_id IS DISTINCT FROM OLD.staging_version_id OR NEW.production_version_id IS DISTINCT FROM OLD.production_version_id)))
          AND nullif(current_setting('woobe.asac_deployment_id',true),'') IS NULL
        THEN RAISE EXCEPTION 'ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("CREATE CONSTRAINT TRIGGER managed_asac_pointer AFTER INSERT OR UPDATE ON network.networks DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION network.check_managed_asac_pointer()")


    op.execute("""CREATE FUNCTION core.guard_asac_policy_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF EXISTS(SELECT 1 FROM core.asac_project_lifecycle_operations WHERE outbox_id=OLD.id) THEN
          IF TG_OP='DELETE' OR
            (to_jsonb(NEW)-ARRAY['status','attempts','last_error','published_at','updated_at','claimed_at','claimed_by','next_attempt_at'])
            IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','attempts','last_error','published_at','updated_at','claimed_at','claimed_by','next_attempt_at'])
          THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_IMMUTABLE'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("CREATE TRIGGER asac_policy_outbox_immutable BEFORE UPDATE OR DELETE ON core.outbox_events FOR EACH ROW EXECUTE FUNCTION core.guard_asac_policy_outbox()")


def downgrade():
    raise RuntimeError('Project lifecycle authority must not be silently disabled; use an audited policy change')
