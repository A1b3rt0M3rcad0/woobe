"""Owner-scoped workflow reservations with database-enforced monotonic fencing."""
from alembic import op
import sqlalchemy as sa

revision='0092'
down_revision='0091'
branch_labels=None
depends_on=None


def upgrade():
    for owner,root in (('agent','agents'),('network','networks')):
        op.create_table('asac_operation_leases',
            sa.Column('id',sa.UUID(),primary_key=True,nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
            sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
            sa.Column('project_id',sa.UUID(),nullable=False),
            sa.Column('resource_id',sa.UUID(),nullable=False),
            sa.Column('scope',sa.String(64),nullable=False),
            sa.Column('lease_id',sa.UUID(),nullable=False),
            sa.Column('workflow_id',sa.UUID(),nullable=False),
            sa.Column('fencing_token',sa.BigInteger(),nullable=False),
            sa.Column('actor',sa.String(96),nullable=False),
            sa.Column('state',sa.String(16),nullable=False),
            sa.Column('acquired_at',sa.DateTime(timezone=True),nullable=False),
            sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
            sa.Column('maximum_expires_at',sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint('project_id','resource_id','scope',name=f'uq_{owner}_asac_lease_scope'),
            sa.CheckConstraint('fencing_token >= 1',name=f'ck_{owner}_asac_lease_fence'),
            sa.CheckConstraint("state IN ('active','released','broken')",name=f'ck_{owner}_asac_lease_state'),
            sa.CheckConstraint('expires_at > acquired_at AND expires_at <= maximum_expires_at',name=f'ck_{owner}_asac_lease_deadline'),
            sa.ForeignKeyConstraint(['resource_id'],[f'{owner}.{root}.id'],ondelete='CASCADE'),schema=owner)
        op.execute(f"""CREATE FUNCTION {owner}.guard_asac_operation_lease() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM {owner}.{root} WHERE id=OLD.resource_id) THEN
              RAISE EXCEPTION 'Retained lease fencing cannot be deleted';
            END IF;
            RETURN OLD;
          END IF;
          IF TG_OP='INSERT' THEN
            IF NEW.fencing_token!=1 OR NEW.state!='active' OR NEW.expires_at<=clock_timestamp()
               OR NEW.maximum_expires_at>NEW.acquired_at+interval '1 day'
            THEN RAISE EXCEPTION 'Lease initialization requires a bounded active first fencing token'; END IF;
            RETURN NEW;
          END IF;
          IF NEW.id IS DISTINCT FROM OLD.id OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.resource_id IS DISTINCT FROM OLD.resource_id OR NEW.scope IS DISTINCT FROM OLD.scope
             OR NEW.created_at IS DISTINCT FROM OLD.created_at
          THEN RAISE EXCEPTION 'Lease scope identity is immutable'; END IF;
          IF NEW.fencing_token=OLD.fencing_token+1 THEN
            IF (OLD.state='active' AND OLD.expires_at>clock_timestamp()) OR NEW.state!='active'
               OR NEW.lease_id=OLD.lease_id OR NEW.expires_at<=clock_timestamp()
               OR NEW.acquired_at<OLD.acquired_at OR NEW.maximum_expires_at>NEW.acquired_at+interval '1 day'
            THEN RAISE EXCEPTION 'Lease replacement requires expiry or release and a new bounded identity'; END IF;
          ELSIF NEW.fencing_token=OLD.fencing_token THEN
            IF NEW.lease_id IS DISTINCT FROM OLD.lease_id OR NEW.workflow_id IS DISTINCT FROM OLD.workflow_id
               OR NEW.actor IS DISTINCT FROM OLD.actor OR NEW.acquired_at IS DISTINCT FROM OLD.acquired_at
               OR NEW.maximum_expires_at IS DISTINCT FROM OLD.maximum_expires_at OR OLD.state!='active'
            THEN RAISE EXCEPTION 'Current lease identity and maximum deadline are immutable'; END IF;
            IF NEW.state='active' THEN
              IF OLD.expires_at<=clock_timestamp() OR NEW.expires_at<=OLD.expires_at
              THEN RAISE EXCEPTION 'Expired leases cannot be renewed or extended indefinitely'; END IF;
            ELSIF NEW.state NOT IN ('released','broken') OR NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
              RAISE EXCEPTION 'Lease terminal transition cannot rewrite its deadline';
            END IF;
          ELSE RAISE EXCEPTION 'Lease fencing token cannot regress or skip a generation'; END IF;
          RETURN NEW;
        END $$""")
        op.execute(f'CREATE TRIGGER guard_asac_operation_lease BEFORE INSERT OR UPDATE OR DELETE ON {owner}.asac_operation_leases FOR EACH ROW EXECUTE FUNCTION {owner}.guard_asac_operation_lease()')

        op.execute(f"""CREATE FUNCTION {owner}.assert_asac_workflow_lease(p_project uuid,p_resource uuid,p_scope text) RETURNS void LANGUAGE plpgsql AS $$
        DECLARE reserved record; proof jsonb; proofs jsonb := '[]'::jsonb; actor text;
        BEGIN
          actor := current_setting('woobe.asac_actor',true);
          IF current_setting('woobe.asac_lease_resource',true)=p_resource::text THEN
            proofs := COALESCE(NULLIF(current_setting('woobe.asac_lease_proofs',true),'')::jsonb,'[]'::jsonb);
          END IF;
          FOR reserved IN SELECT * FROM {owner}.asac_operation_leases
            WHERE project_id=p_project AND resource_id=p_resource AND scope IN ('resource',p_scope) LOOP
            proof := NULL;
            SELECT item INTO proof FROM jsonb_array_elements(proofs) item WHERE item->>'lease_id'=reserved.lease_id::text;
            IF reserved.state='active' AND reserved.expires_at>clock_timestamp() THEN
              IF proof IS NULL OR actor IS DISTINCT FROM reserved.actor
                OR proof->>'workflow_id' IS DISTINCT FROM reserved.workflow_id::text
                OR (proof->>'fencing_token')::bigint IS DISTINCT FROM reserved.fencing_token
              THEN RAISE EXCEPTION 'ASAC_LEASE_FENCED: active authoring reservation requires its exact workflow proof'; END IF;
            ELSIF proof IS NOT NULL THEN
              RAISE EXCEPTION 'ASAC_LEASE_EXPIRED: original workflow cannot write after expiry or release';
            END IF;
          END LOOP;
          FOR proof IN SELECT item FROM jsonb_array_elements(proofs) item LOOP
            IF NOT EXISTS(SELECT 1 FROM {owner}.asac_operation_leases WHERE project_id=p_project
                AND resource_id=p_resource AND scope IN ('resource',p_scope) AND lease_id::text=proof->>'lease_id')
            THEN RAISE EXCEPTION 'ASAC_LEASE_FENCED: original workflow was superseded'; END IF;
          END LOOP;
        END $$""")
        op.execute(f"""CREATE FUNCTION {owner}.check_asac_draft_workflow_lease() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM {owner}.assert_asac_workflow_lease(NEW.project_id,NEW.resource_id,'draft:'||NEW.id::text);
          RETURN NULL;
        END $$""")
        op.execute(f'CREATE CONSTRAINT TRIGGER check_asac_draft_workflow_lease AFTER INSERT OR UPDATE ON {owner}.asac_drafts DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {owner}.check_asac_draft_workflow_lease()')
        if owner=='agent':
            changed="(to_jsonb(NEW)-ARRAY['revision','updated_at','status']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['revision','updated_at','status'])"
        else:
            changed="NEW.draft_definition IS DISTINCT FROM OLD.draft_definition OR NEW.draft_revision IS DISTINCT FROM OLD.draft_revision"
        op.execute(f"""CREATE FUNCTION {owner}.check_asac_native_draft_workflow_lease() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF {changed} THEN
            PERFORM {owner}.assert_asac_workflow_lease(NEW.project_id,NEW.id,'draft:native');
          END IF;
          RETURN NULL;
        END $$""")
        op.execute(f'CREATE CONSTRAINT TRIGGER check_asac_native_draft_workflow_lease AFTER UPDATE ON {owner}.{root} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {owner}.check_asac_native_draft_workflow_lease()')


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM agent.asac_operation_leases)
      OR EXISTS(SELECT 1 FROM network.asac_operation_leases)
      THEN RAISE EXCEPTION 'Retained lease fencing prevents destructive downgrade'; END IF;
    END $$""")
    for owner,root in (('network','networks'),('agent','agents')):
        op.execute(f'DROP TRIGGER check_asac_draft_workflow_lease ON {owner}.asac_drafts')
        op.execute(f'DROP TRIGGER check_asac_native_draft_workflow_lease ON {owner}.{root}')
        op.execute(f'DROP FUNCTION {owner}.check_asac_draft_workflow_lease()')
        op.execute(f'DROP FUNCTION {owner}.check_asac_native_draft_workflow_lease()')
        op.execute(f'DROP FUNCTION {owner}.assert_asac_workflow_lease(uuid,uuid,text)')
        op.drop_table('asac_operation_leases',schema=owner)
        op.execute(f'DROP FUNCTION {owner}.guard_asac_operation_lease()')
