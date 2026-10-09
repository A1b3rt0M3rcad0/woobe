"""Independent immutable Release selections and durable fenced deployments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision='0093'
down_revision='0092'
branch_labels=None
depends_on=None


def _function(owner,name,signature):
    return op.get_bind().execute(sa.text('SELECT pg_get_functiondef(CAST(:name AS regprocedure))'),
        {'name':f'{owner}.{name}({signature})'}).scalar_one()


def upgrade():
    for owner,root,release,outbox in (('agent','agents','agent_releases','agent_outbox_events'),
                                    ('network','networks','network_versions','outbox_events')):
        op.add_column('asac_environment_selections',sa.Column('selection_authority',sa.String(16),nullable=False,server_default='legacy'),schema=owner)
        op.create_check_constraint(f'ck_{owner}_asac_selection_authority','asac_environment_selections',"selection_authority IN ('legacy','asac')",schema=owner)
        op.execute(f"CREATE FUNCTION {owner}.reject_asac_deployment_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'ASaC deployment history is immutable'; END $$")
        for table,plan in (('asac_deployment_plans',True),('asac_deployments',False)):
            columns=[sa.Column('id',UUID(as_uuid=True),primary_key=True,server_default=sa.text('gen_random_uuid()')),
                sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
                sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
                sa.Column('project_id',UUID(as_uuid=True),nullable=False),sa.Column('resource_id',UUID(as_uuid=True),nullable=False),
                sa.Column('publication_id',UUID(as_uuid=True),nullable=False),sa.Column('release_id',UUID(as_uuid=True),nullable=False),
                sa.Column('previous_release_id',UUID(as_uuid=True),nullable=True),
                sa.Column('environment',sa.String(16),nullable=False),sa.Column('actor',sa.String(96),nullable=False),
                sa.Column('operation_id',UUID(as_uuid=True),nullable=False),sa.Column('request_digest',sa.String(71),nullable=False),
                sa.Column('action',sa.String(16),nullable=False),sa.Column('reason',sa.String(2048),nullable=False),
                sa.Column('evidence',JSONB,nullable=False),
                sa.ForeignKeyConstraint(['resource_id'],[f'{owner}.{root}.id'],ondelete='RESTRICT'),
                sa.ForeignKeyConstraint(['release_id'],[f'{owner}.{release}.id'],ondelete='RESTRICT'),
                sa.ForeignKeyConstraint(['publication_id'],[f'{owner}.asac_publications.id'],ondelete='RESTRICT'),
                sa.CheckConstraint("environment IN ('staging','production') AND action IN ('activate','rollback')",name=f'ck_{owner}_{table}_scope'),
                sa.UniqueConstraint('project_id','resource_id','actor','operation_id',name=f'uq_{owner}_{table}_operation')]
            if plan:
                columns.extend([sa.Column('expected_generation',sa.BigInteger(),nullable=False),
                    sa.Column('previous_fingerprint',sa.String(64),nullable=True),
                    sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
                    sa.CheckConstraint('expected_generation >= 0',name=f'ck_{owner}_asac_plan_generation')])
            else:
                columns.extend([sa.Column('plan_id',UUID(as_uuid=True),nullable=False),
                    sa.Column('generation_before',sa.BigInteger(),nullable=False),sa.Column('generation_after',sa.BigInteger(),nullable=False),
                    sa.Column('selection_changed',sa.Boolean(),nullable=False),sa.Column('outbox_id',UUID(as_uuid=True),nullable=False),
                    sa.ForeignKeyConstraint(['plan_id'],[f'{owner}.asac_deployment_plans.id'],ondelete='RESTRICT'),
                    sa.ForeignKeyConstraint(['outbox_id'],[f'{owner}.{outbox}.id'],ondelete='RESTRICT',deferrable=True,initially='DEFERRED'),
                    sa.UniqueConstraint('plan_id',name=f'uq_{owner}_asac_deployment_plan'),
                    sa.CheckConstraint('generation_before >= 0 AND generation_after >= generation_before AND generation_after <= generation_before + 1',name=f'ck_{owner}_asac_deployment_generation')])
            op.create_table(table,*columns,schema=owner)
            op.execute(f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {owner}.{table} FOR EACH ROW EXECUTE FUNCTION {owner}.reject_asac_deployment_mutation()")

        # Authoring and selection are independent reservation scopes. Preserve the
        # already applied lease proof checks; only narrow the scope predicate.
        definition=_function(owner,'assert_asac_workflow_lease','uuid,uuid,text')
        old="scope IN ('resource',p_scope)"
        if definition.count(old)!=2:
            raise RuntimeError('Unexpected applied lease function; refusing an ambiguous migration')
        op.execute(definition.replace(old,"(scope=p_scope OR (p_scope NOT IN ('staging','production') AND scope='resource'))"))

        # New selections are not reverse-derived from legacy Release status. A
        # pointer can reference the same immutable Release in both environments.
        definition=_function(owner,'refresh_asac_environment_selection','uuid')
        needle="FOREACH p_env IN ARRAY ARRAY['staging','production'] LOOP"
        if definition.count(needle)!=1:
            raise RuntimeError('Unexpected applied selection function')
        op.execute(definition.replace(needle,needle+f"\n IF EXISTS(SELECT 1 FROM {owner}.asac_environment_selections WHERE resource_id=p_resource AND environment=p_env AND selection_authority='asac') THEN CONTINUE; END IF;"))

        op.execute(f"""CREATE OR REPLACE FUNCTION {owner}.guard_asac_environment_selection() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE changed boolean;
        BEGIN
          IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM {owner}.{root} WHERE id=OLD.resource_id) THEN
              RAISE EXCEPTION 'Environment selection history cannot be deleted'; END IF;
            RETURN OLD;
          END IF;
          changed := NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id OR NEW.execution_fingerprint IS DISTINCT FROM OLD.execution_fingerprint;
          IF NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.resource_id IS DISTINCT FROM OLD.resource_id
            OR NEW.environment IS DISTINCT FROM OLD.environment OR NEW.id IS DISTINCT FROM OLD.id
            OR NEW.created_at IS DISTINCT FROM OLD.created_at
            OR (OLD.selection_authority='asac' AND NEW.selection_authority!='asac')
            OR NEW.generation != OLD.generation + (CASE WHEN changed THEN 1 ELSE 0 END)
            OR (NOT changed AND NOT (OLD.selection_authority='legacy' AND NEW.selection_authority='asac'))
          THEN RAISE EXCEPTION 'Environment selection generation must advance with changed executable identity'; END IF;
          IF NEW.selection_authority='asac' AND COALESCE(current_setting('woobe.asac_deployment_id',true),'')=''
          THEN RAISE EXCEPTION 'ASAC_DEPLOYMENT_RECEIPT_REQUIRED: selection needs an exact deployment'; END IF;
          PERFORM {owner}.assert_asac_workflow_lease(NEW.project_id,NEW.resource_id,NEW.environment);
          RETURN NEW;
        END $$""")

        op.execute(f"""CREATE FUNCTION {owner}.check_asac_deployment_commit() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE plan record; selected record; reserved record; event record; operation record; proofs jsonb; proof jsonb;
        BEGIN
          SELECT * INTO plan FROM {owner}.asac_deployment_plans WHERE id=NEW.plan_id;
          SELECT * INTO selected FROM {owner}.asac_environment_selections WHERE project_id=NEW.project_id
            AND resource_id=NEW.resource_id AND environment=NEW.environment;
          SELECT * INTO event FROM {owner}.{outbox} WHERE id=NEW.outbox_id;
          SELECT * INTO operation FROM {owner}.asac_operations WHERE project_id=NEW.project_id
            AND resource_id=NEW.resource_id AND actor=NEW.actor AND operation_id=NEW.operation_id;
          IF plan.id IS NULL OR plan.expires_at<=clock_timestamp()
            OR plan.project_id!=NEW.project_id OR plan.resource_id!=NEW.resource_id
            OR plan.release_id!=NEW.release_id OR plan.publication_id!=NEW.publication_id
            OR plan.environment!=NEW.environment OR plan.expected_generation!=NEW.generation_before
            OR plan.previous_release_id IS DISTINCT FROM NEW.previous_release_id
            OR plan.action!=NEW.action OR plan.reason!=NEW.reason
            OR selected.id IS NULL OR selected.snapshot_id IS DISTINCT FROM NEW.release_id OR selected.generation!=NEW.generation_after
            OR selected.selection_authority!='asac' OR selected.execution_fingerprint IS DISTINCT FROM NEW.evidence->>'native_fingerprint'
            OR NEW.generation_after!=NEW.generation_before+(CASE WHEN NEW.selection_changed THEN 1 ELSE 0 END)
            OR event.id IS NULL OR event.aggregate_id!=NEW.resource_id
            OR event.payload->>'deployment_id' IS DISTINCT FROM NEW.id::text
            OR event.payload->>'receipt_digest' IS DISTINCT FROM operation.result->>'receipt_digest'
            OR event.payload IS DISTINCT FROM operation.result
            OR operation.id IS NULL OR operation.request_digest!=NEW.request_digest
            OR operation.result->>'deployment_id' IS DISTINCT FROM NEW.id::text
            OR current_setting('woobe.asac_deployment_id',true) IS DISTINCT FROM NEW.id::text
          THEN RAISE EXCEPTION 'ASAC_DEPLOYMENT_COMMIT_INVALID: selection, plan, receipt and outbox must commit together'; END IF;
          proofs := COALESCE(NULLIF(current_setting('woobe.asac_lease_proofs',true),'')::jsonb,'[]'::jsonb);
          IF jsonb_array_length(proofs)!=1 OR proofs IS DISTINCT FROM NEW.evidence->'leases'
            OR current_setting('woobe.asac_actor',true) IS DISTINCT FROM NEW.actor
            OR current_setting('woobe.asac_lease_resource',true) IS DISTINCT FROM NEW.resource_id::text
          THEN RAISE EXCEPTION 'ASAC_LEASE_FENCED: deployment requires its original exact workflow proof'; END IF;
          proof := proofs->0;
          SELECT * INTO reserved FROM {owner}.asac_operation_leases WHERE project_id=NEW.project_id
            AND resource_id=NEW.resource_id AND scope=NEW.environment;
          IF reserved.lease_id IS NULL OR reserved.lease_id::text IS DISTINCT FROM proof->>'lease_id'
            OR reserved.workflow_id::text IS DISTINCT FROM proof->>'workflow_id'
            OR reserved.fencing_token IS DISTINCT FROM (proof->>'fencing_token')::bigint OR reserved.actor!=NEW.actor
          THEN RAISE EXCEPTION 'ASAC_LEASE_FENCED: deployment workflow was superseded'; END IF;
          IF reserved.state!='active' OR reserved.expires_at<=clock_timestamp()
          THEN RAISE EXCEPTION 'ASAC_LEASE_EXPIRED: deployment lease expired before commit'; END IF;
          RETURN NULL;
        END $$""")
        op.execute(f'CREATE CONSTRAINT TRIGGER check_asac_deployment_commit AFTER INSERT ON {owner}.asac_deployments DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {owner}.check_asac_deployment_commit()')
        op.execute(f"""CREATE FUNCTION {owner}.check_asac_selection_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.selection_authority='asac' AND NOT EXISTS(SELECT 1 FROM {owner}.asac_deployments
            WHERE id::text=current_setting('woobe.asac_deployment_id',true) AND project_id=NEW.project_id
              AND resource_id=NEW.resource_id AND environment=NEW.environment
              AND release_id=NEW.snapshot_id AND generation_after=NEW.generation)
          THEN RAISE EXCEPTION 'ASAC_DEPLOYMENT_RECEIPT_REQUIRED: independent selection has no committed deployment'; END IF;
          RETURN NULL;
        END $$""")
        op.execute(f'CREATE CONSTRAINT TRIGGER check_asac_selection_receipt AFTER UPDATE ON {owner}.asac_environment_selections DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {owner}.check_asac_selection_receipt()')
        op.execute(f"""CREATE FUNCTION {owner}.guard_asac_deployment_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS(SELECT 1 FROM {owner}.asac_deployments WHERE outbox_id=OLD.id)
            AND (NEW.id IS DISTINCT FROM OLD.id OR NEW.payload IS DISTINCT FROM OLD.payload
              OR NEW.aggregate_id IS DISTINCT FROM OLD.aggregate_id OR NEW.aggregate_type IS DISTINCT FROM OLD.aggregate_type
              OR NEW.event_type IS DISTINCT FROM OLD.event_type OR NEW.event_version IS DISTINCT FROM OLD.event_version
              OR NEW.routing_key IS DISTINCT FROM OLD.routing_key OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
              OR NEW.correlation_id IS DISTINCT FROM OLD.correlation_id OR NEW.causation_id IS DISTINCT FROM OLD.causation_id)
          THEN RAISE EXCEPTION 'ASaC deployment outbox evidence is immutable'; END IF;
          RETURN NEW;
        END $$""")
        op.execute(f'CREATE TRIGGER guard_asac_deployment_outbox BEFORE UPDATE ON {owner}.{outbox} FOR EACH ROW EXECUTE FUNCTION {owner}.guard_asac_deployment_outbox()')

    op.execute("""CREATE FUNCTION agent.guard_legacy_asac_selection() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE root_id uuid; env text;
    BEGIN
      root_id := CASE WHEN TG_OP='DELETE' THEN OLD.agent_id ELSE NEW.agent_id END;
      FOREACH env IN ARRAY ARRAY['staging','production'] LOOP
        IF EXISTS(SELECT 1 FROM agent.asac_environment_selections WHERE resource_id=root_id
          AND environment=env AND selection_authority='asac')
          AND ((TG_OP!='INSERT' AND OLD.status=env) OR (TG_OP!='DELETE' AND NEW.status=env))
        THEN RAISE EXCEPTION 'ASAC_SELECTION_MANAGED: use an exact Release deployment plan'; END IF;
      END LOOP;
      RETURN NULL;
    END $$""")
    op.execute('CREATE CONSTRAINT TRIGGER guard_legacy_asac_selection AFTER INSERT OR UPDATE OR DELETE ON agent.agent_releases DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION agent.guard_legacy_asac_selection()')
    op.execute("""CREATE FUNCTION network.guard_legacy_asac_selection() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE env text; target uuid;
    BEGIN
      FOREACH env IN ARRAY ARRAY['staging','production'] LOOP
        target := CASE WHEN env='staging' THEN NEW.staging_version_id ELSE NEW.production_version_id END;
        IF (CASE WHEN env='staging' THEN NEW.staging_version_id IS DISTINCT FROM OLD.staging_version_id
            ELSE NEW.production_version_id IS DISTINCT FROM OLD.production_version_id END)
          AND EXISTS(SELECT 1 FROM network.asac_environment_selections WHERE resource_id=NEW.id
            AND environment=env AND selection_authority='asac')
          AND NOT EXISTS(SELECT 1 FROM network.asac_deployments WHERE id::text=current_setting('woobe.asac_deployment_id',true)
            AND resource_id=NEW.id AND project_id=NEW.project_id AND environment=env AND release_id=target)
        THEN RAISE EXCEPTION 'ASAC_SELECTION_MANAGED: use an exact Release deployment plan'; END IF;
      END LOOP;
      RETURN NULL;
    END $$""")
    op.execute('CREATE CONSTRAINT TRIGGER guard_legacy_asac_selection AFTER UPDATE ON network.networks DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION network.guard_legacy_asac_selection()')


def downgrade():
    raise RuntimeError('Independent selection authority and retained deployment evidence require an explicit forward migration')
