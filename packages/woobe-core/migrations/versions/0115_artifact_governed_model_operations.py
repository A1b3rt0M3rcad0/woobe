"""Governed document model operations with actual mutable model revisions."""
from alembic import op
import sqlalchemy as sa

revision = '0115'
down_revision = '0114'
branch_labels = None
depends_on = None


# Frozen SQL: migrations never import mutable application metadata.
MODEL_CALL_DDL = "\nCREATE TABLE artifacts.document_model_calls (\n\tid VARCHAR(128) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tenvironment VARCHAR(16) NOT NULL, \n\tworkspace_id VARCHAR(128) NOT NULL, \n\tjob_id VARCHAR(128) NOT NULL, \n\toperation_key VARCHAR(128) NOT NULL, \n\toperation VARCHAR(32) NOT NULL, \n\tinput_fingerprint VARCHAR(64) NOT NULL, \n\tbinding_fingerprint VARCHAR(64) NOT NULL, \n\tfencing_token BIGINT NOT NULL, \n\tnonce VARCHAR(128) NOT NULL, \n\tstate VARCHAR(16) NOT NULL, \n\tbudget_tokens BIGINT NOT NULL, \n\tmax_output_tokens INTEGER NOT NULL, \n\tinput_tokens BIGINT, \n\toutput_tokens BIGINT, \n\tcost_usd NUMERIC(24, 10), \n\tcost_status VARCHAR(16) NOT NULL, \n\tprovider_request_id VARCHAR(255), \n\tresponse JSONB, \n\tresponse_sha256 VARCHAR(64), \n\terror_code VARCHAR(128), \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tobservation_revision INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_artifact_document_model_operation UNIQUE (job_id, operation_key), \n\tCONSTRAINT fk_artifact_document_model_job FOREIGN KEY(project_id, environment, workspace_id, job_id) REFERENCES artifacts.processing_jobs (project_id, environment, workspace_id, id), \n\tCONSTRAINT fk_artifact_document_model_attempt FOREIGN KEY(job_id, fencing_token) REFERENCES artifacts.processing_attempts (job_id, fencing_token), \n\tCONSTRAINT ck_artifact_document_model_operation CHECK (operation IN ('summarize','refine_structure')), \n\tCONSTRAINT ck_artifact_document_model_state CHECK (state IN ('admitted','in_flight','completed','failed','uncertain')), \n\tCONSTRAINT ck_artifact_document_model_digests CHECK (input_fingerprint ~ '^[0-9a-f]{64}$' AND binding_fingerprint ~ '^[0-9a-f]{64}$'), \n\tCONSTRAINT ck_artifact_document_model_bounds CHECK (fencing_token >= 1 AND budget_tokens >= 0 AND max_output_tokens >= 1 AND max_output_tokens <= 32768 AND observation_revision >= 0), \n\tCONSTRAINT ck_artifact_document_model_usage CHECK ((input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND (cost_usd IS NULL OR cost_usd >= 0)), \n\tCONSTRAINT ck_artifact_document_model_cost_status CHECK (cost_status IN ('reported','estimated','unknown')), \n\tCONSTRAINT ck_artifact_document_model_result CHECK ((state = 'completed' AND response IS NOT NULL AND response_sha256 ~ '^[0-9a-f]{64}$') OR (state <> 'completed' AND response IS NULL AND response_sha256 IS NULL)), \n\tCONSTRAINT ck_artifact_document_model_response_bound CHECK (response IS NULL OR octet_length(response::text) <= 262144)\n)\n\n"
MODEL_CALL_INDEX_DDL = ['CREATE INDEX ix_artifact_document_model_job_budget ON artifacts.document_model_calls (job_id, state)']

def upgrade():
    op.add_column('processing_jobs', sa.Column('model_binding', sa.dialects.postgresql.JSONB(none_as_null=True), nullable=True), schema='artifacts')
    op.execute(MODEL_CALL_DDL)
    for statement in MODEL_CALL_INDEX_DDL:
        op.execute(statement)
    op.execute("""CREATE FUNCTION artifacts.guard_job_model_binding() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.model_binding IS DISTINCT FROM OLD.model_binding THEN
        RAISE EXCEPTION 'accepted document model binding is immutable';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER immutable_job_model_binding BEFORE UPDATE ON artifacts.processing_jobs FOR EACH ROW EXECUTE FUNCTION artifacts.guard_job_model_binding()')
    op.execute("""CREATE FUNCTION artifacts.guard_document_model_call() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'document model operation evidence must be retained';
      END IF;
      IF (to_jsonb(NEW) - ARRAY['state','nonce','fencing_token','input_tokens','output_tokens','cost_usd','cost_status',
          'provider_request_id','response','response_sha256','error_code','started_at','finished_at','observation_revision'])
         IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['state','nonce','fencing_token','input_tokens','output_tokens','cost_usd','cost_status',
          'provider_request_id','response','response_sha256','error_code','started_at','finished_at','observation_revision']) THEN
        RAISE EXCEPTION 'document model admitted operation identity is immutable';
      END IF;
      IF OLD.state IN ('completed','failed') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal document model evidence is immutable';
      END IF;
      IF OLD.state <> 'admitted' AND (NEW.nonce, NEW.fencing_token) IS DISTINCT FROM (OLD.nonce, OLD.fencing_token) THEN
        RAISE EXCEPTION 'dispatched document model owner is immutable';
      END IF;
      IF (OLD.state <> 'admitted' AND NEW.state = 'admitted') OR
         (OLD.state = 'uncertain' AND NEW.state = 'in_flight') THEN
        RAISE EXCEPTION 'dispatched document model operation cannot retry';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER immutable_document_model_call BEFORE UPDATE OR DELETE ON artifacts.document_model_calls FOR EACH ROW EXECUTE FUNCTION artifacts.guard_document_model_call()')
    op.add_column('provider_models' , sa.Column('definition_revision', sa.BigInteger(), nullable=False, server_default='1'), schema='agent')
    op.create_check_constraint('ck_provider_model_definition_revision', 'provider_models', 'definition_revision >= 1', schema='agent')
    op.execute("""CREATE FUNCTION agent.bump_provider_model_definition_revision() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (to_jsonb(NEW) - ARRAY['definition_revision','updated_at']) IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['definition_revision','updated_at']) THEN
        NEW.definition_revision = OLD.definition_revision + 1;
      ELSE
        NEW.definition_revision = OLD.definition_revision;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER bump_provider_model_definition_revision BEFORE UPDATE ON agent.provider_models FOR EACH ROW EXECUTE FUNCTION agent.bump_provider_model_definition_revision()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM artifacts.document_model_calls) OR EXISTS (SELECT 1 FROM artifacts.processing_jobs WHERE model_binding IS NOT NULL)')):
        raise RuntimeError('Governed model operation evidence must be retained')
    op.execute('DROP TRIGGER immutable_job_model_binding ON artifacts.processing_jobs')
    op.execute('DROP FUNCTION artifacts.guard_job_model_binding()')
    op.execute('DROP TRIGGER immutable_document_model_call ON artifacts.document_model_calls')
    op.execute('DROP FUNCTION artifacts.guard_document_model_call()')
    op.drop_table('document_model_calls', schema='artifacts')
    op.drop_column('processing_jobs', 'model_binding', schema='artifacts')
    op.execute('DROP TRIGGER bump_provider_model_definition_revision ON agent.provider_models')
    op.execute('DROP FUNCTION agent.bump_provider_model_definition_revision()')
    op.drop_constraint('ck_provider_model_definition_revision', 'provider_models', schema='agent')
    op.drop_column('provider_models', 'definition_revision', schema='agent')
