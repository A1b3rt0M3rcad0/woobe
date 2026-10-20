"""Coherent immutable representation sets and durably charged output objects."""
from alembic import op
import sqlalchemy as sa

revision = '0113'
down_revision = '0112'
branch_labels = None
depends_on = None

# Frozen PostgreSQL DDL: this migration never imports evolving runtime models.
TABLE_DDL = (
    """
CREATE TABLE artifacts.stored_objects (
	project_id UUID NOT NULL,
	environment VARCHAR(16) NOT NULL,
	workspace_id VARCHAR(128) NOT NULL,
	job_id VARCHAR(128) NOT NULL,
	fencing_token BIGINT NOT NULL,
	object_key VARCHAR(1024) NOT NULL,
	role VARCHAR(32) NOT NULL,
	size_bytes BIGINT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	content_type VARCHAR(255) NOT NULL,
	storage_version_id VARCHAR(1024),
	state VARCHAR(32) NOT NULL,
	accounting_bucket VARCHAR(16) NOT NULL,
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_stored_object_scope UNIQUE (workspace_id, id),
	CONSTRAINT uq_artifact_stored_object_key UNIQUE (workspace_id, object_key),
	CONSTRAINT fk_artifact_stored_object_job FOREIGN KEY(project_id, environment, workspace_id, job_id) REFERENCES artifacts.processing_jobs (project_id, environment, workspace_id, id),
	CONSTRAINT ck_artifact_stored_object_bounds CHECK (size_bytes >= 0 AND fencing_token >= 1),
	CONSTRAINT ck_artifact_stored_object_digest CHECK (sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_artifact_stored_object_state CHECK (state IN ('reserved','stored','referenced','gc_pending','purged')),
	CONSTRAINT ck_artifact_stored_object_accounting CHECK (accounting_bucket IN ('reserved','used','none')),
	CONSTRAINT ck_artifact_stored_object_state_accounting CHECK ((state = 'reserved' AND accounting_bucket = 'reserved') OR (state IN ('stored','referenced') AND accounting_bucket = 'used') OR (state = 'gc_pending' AND accounting_bucket IN ('reserved','used')) OR (state = 'purged' AND accounting_bucket = 'none'))
)
""",
    """
CREATE INDEX ix_artifact_stored_object_gc ON artifacts.stored_objects (workspace_id, state, created_at)
""",
    """
CREATE TABLE artifacts.representation_sets (
	project_id UUID NOT NULL,
	environment VARCHAR(16) NOT NULL,
	workspace_id VARCHAR(128) NOT NULL,
	artifact_id VARCHAR(128) NOT NULL,
	revision_id VARCHAR(128) NOT NULL,
	job_id VARCHAR(128) NOT NULL,
	generation_number BIGINT NOT NULL,
	build_fencing_token BIGINT NOT NULL,
	publication_fencing_token BIGINT NOT NULL,
	source_sha256 VARCHAR(64) NOT NULL,
	recipe_fingerprint VARCHAR(64) NOT NULL,
	processing_fingerprint VARCHAR(64) NOT NULL,
	profile_id VARCHAR(128),
	profile_revision BIGINT,
	status VARCHAR(32) NOT NULL,
	coverage VARCHAR(32) NOT NULL,
	manifest_object_id VARCHAR(128),
	manifest_sha256 VARCHAR(64),
	metadata_fingerprint VARCHAR(64),
	sealed BOOLEAN NOT NULL,
	entry_count INTEGER NOT NULL,
	block_count INTEGER NOT NULL,
	segment_count INTEGER NOT NULL,
	page_count INTEGER NOT NULL,
	diagnostics JSONB NOT NULL,
	pages JSONB NOT NULL,
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_representation_set_scope UNIQUE (workspace_id, id),
	CONSTRAINT uq_artifact_representation_source_identity UNIQUE (workspace_id, artifact_id, revision_id, id),
	CONSTRAINT uq_artifact_representation_job UNIQUE (job_id),
	CONSTRAINT fk_artifact_representation_source_job FOREIGN KEY(workspace_id, artifact_id, revision_id, job_id) REFERENCES artifacts.processing_jobs (workspace_id, artifact_id, revision_id, id),
	CONSTRAINT fk_artifact_representation_scope FOREIGN KEY(project_id, environment, workspace_id) REFERENCES artifacts.workspaces (project_id, environment, id),
	CONSTRAINT fk_artifact_representation_manifest FOREIGN KEY(workspace_id, manifest_object_id) REFERENCES artifacts.stored_objects (workspace_id, id),
	CONSTRAINT ck_artifact_representation_status CHECK (status IN ('building','ready','deletion_pending','purged')),
	CONSTRAINT ck_artifact_representation_bounds CHECK (generation_number >= 0 AND build_fencing_token >= 1 AND publication_fencing_token >= 0),
	CONSTRAINT ck_artifact_representation_counts CHECK (entry_count >= 0 AND block_count >= 0 AND segment_count >= 0 AND page_count >= 0),
	CONSTRAINT ck_artifact_representation_coverage CHECK (coverage IN ('complete','partial','needs_ocr','unsupported')),
	CONSTRAINT ck_artifact_representation_digests CHECK (source_sha256 ~ '^[0-9a-f]{64}$' AND recipe_fingerprint ~ '^[0-9a-f]{64}$' AND processing_fingerprint ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_artifact_representation_profile_pair CHECK ((profile_id IS NULL) = (profile_revision IS NULL)),
	CONSTRAINT fk_artifact_representation_profile FOREIGN KEY(project_id, environment, profile_id, profile_revision) REFERENCES artifacts.processing_profiles (project_id, environment, id, revision)
)
""",
    """
CREATE INDEX ix_artifact_representation_page ON artifacts.representation_sets (workspace_id, artifact_id, revision_id, generation_number, id)
""",
    """
CREATE INDEX ix_artifact_representation_reuse ON artifacts.representation_sets (workspace_id, artifact_id, revision_id, processing_fingerprint, status)
""",
    """
CREATE TABLE artifacts.representation_entries (
	workspace_id VARCHAR(128) NOT NULL,
	representation_set_id VARCHAR(128) NOT NULL,
	object_id VARCHAR(128) NOT NULL,
	path VARCHAR(1024) NOT NULL,
	role VARCHAR(32) NOT NULL,
	visible BOOLEAN NOT NULL,
	asset_id VARCHAR(128),
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_representation_entry_scope UNIQUE (workspace_id, representation_set_id, id),
	CONSTRAINT uq_artifact_representation_path UNIQUE (representation_set_id, path),
	CONSTRAINT uq_artifact_representation_asset UNIQUE (representation_set_id, asset_id),
	CONSTRAINT fk_artifact_representation_entry_set FOREIGN KEY(workspace_id, representation_set_id) REFERENCES artifacts.representation_sets (workspace_id, id),
	CONSTRAINT fk_artifact_representation_entry_object FOREIGN KEY(workspace_id, object_id) REFERENCES artifacts.stored_objects (workspace_id, id)
)
""",
    """
CREATE INDEX ix_artifact_representation_entry_page ON artifacts.representation_entries (representation_set_id, path, id)
""",
    """
CREATE TABLE artifacts.source_blocks (
	workspace_id VARCHAR(128) NOT NULL,
	representation_set_id VARCHAR(128) NOT NULL,
	block_id VARCHAR(128) NOT NULL,
	ordinal INTEGER NOT NULL,
	kind VARCHAR(32) NOT NULL,
	parent_block_id VARCHAR(128),
	source_locator JSONB NOT NULL,
	extraction_method VARCHAR(16) NOT NULL,
	inferred BOOLEAN NOT NULL,
	asset_ids JSONB NOT NULL,
	object_id VARCHAR(128),
	byte_start BIGINT NOT NULL,
	byte_end BIGINT NOT NULL,
	char_length BIGINT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_source_block_scope UNIQUE (workspace_id, representation_set_id, block_id),
	CONSTRAINT uq_artifact_source_block_ordinal UNIQUE (representation_set_id, ordinal),
	CONSTRAINT fk_artifact_source_block_set FOREIGN KEY(workspace_id, representation_set_id) REFERENCES artifacts.representation_sets (workspace_id, id),
	CONSTRAINT fk_artifact_source_block_object FOREIGN KEY(workspace_id, object_id) REFERENCES artifacts.stored_objects (workspace_id, id),
	CONSTRAINT fk_artifact_source_block_parent FOREIGN KEY(workspace_id, representation_set_id, parent_block_id) REFERENCES artifacts.source_blocks (workspace_id, representation_set_id, block_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT ck_artifact_source_block_bounds CHECK (ordinal >= 0 AND char_length >= 0 AND byte_start >= 0 AND byte_end >= byte_start),
	CONSTRAINT ck_artifact_source_block_digest CHECK (sha256 ~ '^[0-9a-f]{64}$')
)
""",
    """
CREATE INDEX ix_artifact_source_block_page ON artifacts.source_blocks (representation_set_id, ordinal)
""",
    """
CREATE TABLE artifacts.source_segments (
	workspace_id VARCHAR(128) NOT NULL,
	representation_set_id VARCHAR(128) NOT NULL,
	block_id VARCHAR(128) NOT NULL,
	char_start BIGINT NOT NULL,
	char_end BIGINT NOT NULL,
	byte_start BIGINT NOT NULL,
	byte_end BIGINT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_source_segment_start UNIQUE (representation_set_id, block_id, char_start),
	CONSTRAINT fk_artifact_source_segment_block FOREIGN KEY(workspace_id, representation_set_id, block_id) REFERENCES artifacts.source_blocks (workspace_id, representation_set_id, block_id),
	CONSTRAINT ck_artifact_source_segment_bounds CHECK (char_start >= 0 AND char_end > char_start AND byte_start >= 0 AND byte_end > byte_start),
	CONSTRAINT ck_artifact_source_segment_digest CHECK (sha256 ~ '^[0-9a-f]{64}$')
)
""",
    """
CREATE TABLE artifacts.representation_heads (
	workspace_id VARCHAR(128) NOT NULL,
	artifact_id VARCHAR(128) NOT NULL,
	revision_id VARCHAR(128) NOT NULL,
	representation_set_id VARCHAR(128) NOT NULL,
	request_number BIGINT NOT NULL,
	PRIMARY KEY (workspace_id, revision_id),
	CONSTRAINT fk_artifact_representation_head_source FOREIGN KEY(workspace_id, artifact_id, revision_id) REFERENCES artifacts.revisions (workspace_id, artifact_id, id),
	CONSTRAINT fk_artifact_representation_head_set FOREIGN KEY(workspace_id, artifact_id, revision_id, representation_set_id) REFERENCES artifacts.representation_sets (workspace_id, artifact_id, revision_id, id),
	CONSTRAINT ck_artifact_representation_head_number CHECK (request_number >= 0)
)
""",
)


def upgrade():
    op.add_column('workspaces', sa.Column('processing_sequence', sa.BigInteger(), nullable=False, server_default='0'), schema='artifacts')
    op.add_column('processing_jobs', sa.Column('generation_number', sa.BigInteger(), nullable=False, server_default='0'), schema='artifacts')
    op.execute("""WITH ordered AS (
        SELECT id, row_number() OVER (PARTITION BY workspace_id ORDER BY created_at, id) AS number
        FROM artifacts.processing_jobs WHERE recipe ->> 'mode' <> 'store_only'
    ) UPDATE artifacts.processing_jobs AS job SET generation_number=ordered.number FROM ordered WHERE ordered.id=job.id""")
    op.execute("""UPDATE artifacts.workspaces AS workspace SET processing_sequence=counts.number
        FROM (SELECT workspace_id, max(generation_number) AS number FROM artifacts.processing_jobs GROUP BY workspace_id) AS counts
        WHERE workspace.id=counts.workspace_id""")
    op.create_check_constraint('ck_artifact_workspace_processing_sequence', 'workspaces', 'processing_sequence >= 0', schema='artifacts')
    op.create_check_constraint('ck_artifact_job_generation', 'processing_jobs', 'generation_number >= 0', schema='artifacts')
    op.create_unique_constraint('uq_artifact_revision_scoped_identity', 'revisions', ['workspace_id','artifact_id','id'], schema='artifacts')
    op.create_unique_constraint('uq_artifact_job_scoped_identity', 'processing_jobs', ['project_id','environment','workspace_id','id'], schema='artifacts')
    op.create_unique_constraint('uq_artifact_job_source_identity', 'processing_jobs', ['workspace_id','artifact_id','revision_id','id'], schema='artifacts')
    for statement in TABLE_DDL:
        op.execute(statement)
    _publication_guards()


def _publication_guards():
    for table in ('revisions', 'uploads'):
        op.add_column(table, sa.Column('source_representation_set_id', sa.String(128)), schema='artifacts')
        op.add_column(table, sa.Column('source_representation_entry_id', sa.String(128)), schema='artifacts')
        op.create_check_constraint(f'ck_artifact_{table}_representation_pair', table,
            '(source_representation_set_id IS NULL) = (source_representation_entry_id IS NULL)', schema='artifacts')
        op.create_foreign_key(f'fk_artifact_{table}_representation', table, 'representation_entries',
            ['workspace_id', 'source_representation_set_id', 'source_representation_entry_id'],
            ['workspace_id', 'representation_set_id', 'id'], source_schema='artifacts', referent_schema='artifacts')
    op.execute("""CREATE FUNCTION artifacts.guard_representation_metadata() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE old_locked boolean; new_locked boolean;
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        SELECT sealed AND status IN ('building','ready') INTO old_locked FROM artifacts.representation_sets WHERE id=OLD.representation_set_id;
      END IF;
      IF TG_OP <> 'DELETE' THEN
        SELECT sealed AND status IN ('building','ready') INTO new_locked FROM artifacts.representation_sets WHERE id=NEW.representation_set_id;
      END IF;
      IF coalesce(old_locked,false) OR coalesce(new_locked,false) THEN
        RAISE EXCEPTION 'sealed representation metadata is immutable';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$""")
    for table in ('representation_entries','source_blocks','source_segments'):
        op.execute(f'CREATE TRIGGER immutable_{table} BEFORE INSERT OR UPDATE OR DELETE ON artifacts.{table} FOR EACH ROW EXECUTE FUNCTION artifacts.guard_representation_metadata()')
    op.execute("""CREATE FUNCTION artifacts.guard_representation_set() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE actual_count bigint; source_hash text; job_recipe text;
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'building' OR NEW.sealed THEN RAISE EXCEPTION 'representation must begin unsealed'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.sealed AND (to_jsonb(NEW) - ARRAY['status','publication_fencing_token']) IS DISTINCT FROM
                        (to_jsonb(OLD) - ARRAY['status','publication_fencing_token']) THEN
        RAISE EXCEPTION 'sealed representation set is immutable';
      END IF;
      IF OLD.status = 'ready' AND NEW.status NOT IN ('ready','deletion_pending') THEN
        RAISE EXCEPTION 'ready representation cannot be rewritten';
      END IF;
      IF NEW.status = 'ready' AND OLD.status <> 'ready' THEN
        IF NOT NEW.sealed OR NEW.manifest_object_id IS NULL OR NEW.manifest_sha256 IS NULL THEN
          RAISE EXCEPTION 'ready representation requires a sealed manifest';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM artifacts.processing_jobs WHERE id=NEW.job_id
                       AND status='running' AND fencing_token=NEW.publication_fencing_token
                       AND lease_until > clock_timestamp() AND processing_fingerprint=NEW.processing_fingerprint
                       AND generation_number=NEW.generation_number) THEN
          RAISE EXCEPTION 'representation publication requires the current live job fence';
        END IF;
        SELECT sha256 INTO source_hash FROM artifacts.revisions WHERE id=NEW.revision_id AND artifact_id=NEW.artifact_id AND workspace_id=NEW.workspace_id;
        SELECT recipe_fingerprint INTO job_recipe FROM artifacts.processing_jobs WHERE id=NEW.job_id;
        IF source_hash IS DISTINCT FROM NEW.source_sha256 OR job_recipe IS DISTINCT FROM NEW.recipe_fingerprint THEN
          RAISE EXCEPTION 'representation source or recipe mismatch';
        END IF;
        SELECT count(*) INTO actual_count FROM artifacts.representation_entries WHERE representation_set_id=NEW.id;
        IF actual_count <> NEW.entry_count THEN RAISE EXCEPTION 'representation entry manifest is incomplete'; END IF;
        SELECT count(*) INTO actual_count FROM artifacts.source_blocks WHERE representation_set_id=NEW.id;
        IF actual_count <> NEW.block_count THEN RAISE EXCEPTION 'representation source map is incomplete'; END IF;
        SELECT count(*) INTO actual_count FROM artifacts.source_segments WHERE representation_set_id=NEW.id;
        IF actual_count <> NEW.segment_count THEN RAISE EXCEPTION 'representation source ranges are incomplete'; END IF;
        IF EXISTS (SELECT 1 FROM artifacts.representation_entries AS entry JOIN artifacts.stored_objects AS object ON object.id=entry.object_id
                   WHERE entry.representation_set_id=NEW.id AND (object.state NOT IN ('stored','referenced') OR object.job_id <> NEW.job_id)) THEN
          RAISE EXCEPTION 'representation contains unverified or foreign objects';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM artifacts.stored_objects WHERE id=NEW.manifest_object_id AND workspace_id=NEW.workspace_id
                       AND job_id=NEW.job_id AND state IN ('stored','referenced') AND sha256=NEW.manifest_sha256) THEN
          RAISE EXCEPTION 'representation manifest object is unverified';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER immutable_representation_set BEFORE INSERT OR UPDATE ON artifacts.representation_sets FOR EACH ROW EXECUTE FUNCTION artifacts.guard_representation_set()')


def downgrade():
    for table in ('revisions', 'uploads'):
        op.drop_constraint(f'fk_artifact_{table}_representation', table, schema='artifacts')
        op.drop_constraint(f'ck_artifact_{table}_representation_pair', table, schema='artifacts')
        op.drop_column(table, 'source_representation_entry_id', schema='artifacts')
        op.drop_column(table, 'source_representation_set_id', schema='artifacts')
    for table in ('representation_entries','source_blocks','source_segments'):
        op.execute(f'DROP TRIGGER immutable_{table} ON artifacts.{table}')
    op.execute('DROP TRIGGER immutable_representation_set ON artifacts.representation_sets')
    op.execute('DROP FUNCTION artifacts.guard_representation_metadata()')
    op.execute('DROP FUNCTION artifacts.guard_representation_set()')
    for table in ('representation_heads','source_segments','source_blocks','representation_entries','representation_sets','stored_objects'):
        op.drop_table(table, schema='artifacts')
    op.drop_constraint('uq_artifact_job_source_identity','processing_jobs',schema='artifacts')
    op.drop_constraint('uq_artifact_job_scoped_identity','processing_jobs',schema='artifacts')
    op.drop_constraint('uq_artifact_revision_scoped_identity','revisions',schema='artifacts')
    op.drop_constraint('ck_artifact_job_generation','processing_jobs',schema='artifacts')
    op.drop_constraint('ck_artifact_workspace_processing_sequence','workspaces',schema='artifacts')
    op.drop_column('processing_jobs','generation_number',schema='artifacts')
    op.drop_column('workspaces','processing_sequence',schema='artifacts')
