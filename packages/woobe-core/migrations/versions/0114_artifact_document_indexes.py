"""Versioned native structural trees pinned to immutable canonical generations."""
from alembic import op

revision = '0114'
down_revision = '0113'
branch_labels = None
depends_on = None

# Frozen PostgreSQL DDL, independent of evolving runtime model imports.
TABLE_DDL = (
    """
CREATE TABLE artifacts.document_indexes (
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	project_id UUID NOT NULL,
	environment VARCHAR(16) NOT NULL,
	workspace_id VARCHAR(128) NOT NULL,
	artifact_id VARCHAR(128) NOT NULL,
	revision_id VARCHAR(128) NOT NULL,
	representation_set_id VARCHAR(128) NOT NULL,
	job_id VARCHAR(128) NOT NULL,
	source_sha256 VARCHAR(64) NOT NULL,
	recipe_fingerprint VARCHAR(64) NOT NULL,
	processing_fingerprint VARCHAR(64) NOT NULL,
	engine VARCHAR(128) NOT NULL,
	engine_version VARCHAR(64) NOT NULL,
	build_fencing_token BIGINT NOT NULL,
	publication_fencing_token BIGINT NOT NULL,
	status VARCHAR(32) NOT NULL,
	sealed BOOLEAN NOT NULL,
	tree_kind VARCHAR(16) NOT NULL,
	coverage VARCHAR(16) NOT NULL,
	root_node_id VARCHAR(128),
	node_count INTEGER NOT NULL,
	source_block_count INTEGER NOT NULL,
	max_depth INTEGER NOT NULL,
	manifest_object_id VARCHAR(128),
	manifest_sha256 VARCHAR(64),
	metadata_fingerprint VARCHAR(64),
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_document_index_generation UNIQUE (workspace_id, representation_set_id, id),
	CONSTRAINT uq_artifact_document_index_job UNIQUE (job_id),
	CONSTRAINT fk_artifact_document_index_generation FOREIGN KEY(workspace_id, artifact_id, revision_id, representation_set_id) REFERENCES artifacts.representation_sets (workspace_id, artifact_id, revision_id, id),
	CONSTRAINT fk_artifact_document_index_source_job FOREIGN KEY(workspace_id, artifact_id, revision_id, job_id) REFERENCES artifacts.processing_jobs (workspace_id, artifact_id, revision_id, id),
	CONSTRAINT fk_artifact_document_index_job FOREIGN KEY(project_id, environment, workspace_id, job_id) REFERENCES artifacts.processing_jobs (project_id, environment, workspace_id, id),
	CONSTRAINT fk_artifact_document_index_manifest FOREIGN KEY(workspace_id, manifest_object_id) REFERENCES artifacts.stored_objects (workspace_id, id),
	CONSTRAINT ck_artifact_document_index_status CHECK (status IN ('building','ready','deletion_pending','purged')),
	CONSTRAINT ck_artifact_document_index_kind CHECK (tree_kind IN ('headings','canonical','pages','blocks','empty')),
	CONSTRAINT ck_artifact_document_index_coverage CHECK (coverage IN ('complete','partial','needs_ocr','unsupported')),
	CONSTRAINT ck_artifact_document_index_bounds CHECK (build_fencing_token >= 1 AND publication_fencing_token >= 0 AND node_count >= 0 AND node_count <= 110001 AND source_block_count >= 0 AND source_block_count <= 100000 AND max_depth >= 0 AND max_depth <= 64),
	CONSTRAINT ck_artifact_document_index_digests CHECK (source_sha256 ~ '^[0-9a-f]{64}$' AND recipe_fingerprint ~ '^[0-9a-f]{64}$' AND processing_fingerprint ~ '^[0-9a-f]{64}$')
)
    """,
    """CREATE INDEX ix_artifact_document_index_reuse ON artifacts.document_indexes (workspace_id, representation_set_id, processing_fingerprint, status)
    """,
    """
CREATE TABLE artifacts.document_nodes (
	id VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	workspace_id VARCHAR(128) NOT NULL,
	representation_set_id VARCHAR(128) NOT NULL,
	document_index_id VARCHAR(128) NOT NULL,
	parent_id VARCHAR(128),
	title VARCHAR(512) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	ordinal INTEGER NOT NULL,
	depth INTEGER NOT NULL,
	children_count INTEGER NOT NULL,
	source_ranges JSONB NOT NULL,
	block_id VARCHAR(128),
	block_sha256 VARCHAR(64),
	page_index INTEGER,
	PRIMARY KEY (id),
	CONSTRAINT uq_artifact_document_node_scope UNIQUE (workspace_id, document_index_id, id),
	CONSTRAINT uq_artifact_document_node_ordinal UNIQUE (document_index_id, ordinal),
	CONSTRAINT uq_artifact_document_node_block UNIQUE (document_index_id, block_id),
	CONSTRAINT fk_artifact_document_node_index FOREIGN KEY(workspace_id, representation_set_id, document_index_id) REFERENCES artifacts.document_indexes (workspace_id, representation_set_id, id),
	CONSTRAINT fk_artifact_document_node_parent FOREIGN KEY(workspace_id, document_index_id, parent_id) REFERENCES artifacts.document_nodes (workspace_id, document_index_id, id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_artifact_document_node_source FOREIGN KEY(workspace_id, representation_set_id, block_id) REFERENCES artifacts.source_blocks (workspace_id, representation_set_id, block_id),
	CONSTRAINT ck_artifact_document_node_bounds CHECK (ordinal >= 0 AND depth >= 0 AND depth <= 64 AND children_count >= 0 AND (page_index IS NULL OR page_index >= 0)),
	CONSTRAINT ck_artifact_document_node_kind CHECK (kind IN ('root','section','page','block')),
	CONSTRAINT ck_artifact_document_node_source_pair CHECK ((block_id IS NULL) = (block_sha256 IS NULL)),
	CONSTRAINT ck_artifact_document_node_digest CHECK (block_sha256 IS NULL OR block_sha256 ~ '^[0-9a-f]{64}$')
)
    """,
    """CREATE INDEX ix_artifact_document_node_children ON artifacts.document_nodes (document_index_id, parent_id, ordinal)
    """,
    """ALTER TABLE artifacts.document_indexes ADD CONSTRAINT fk_artifact_document_index_root_node FOREIGN KEY(workspace_id, id, root_node_id) REFERENCES artifacts.document_nodes (workspace_id, document_index_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
)


def upgrade():
    for statement in TABLE_DDL:
        op.execute(statement)
    _guards()


def _guards():
    op.execute("""CREATE FUNCTION artifacts.guard_document_node() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE old_locked boolean; new_locked boolean;
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        SELECT sealed AND status IN ('building','ready') INTO old_locked FROM artifacts.document_indexes WHERE id=OLD.document_index_id;
      END IF;
      IF TG_OP <> 'DELETE' THEN
        SELECT sealed AND status IN ('building','ready') INTO new_locked FROM artifacts.document_indexes WHERE id=NEW.document_index_id;
      END IF;
      IF coalesce(old_locked,false) OR coalesce(new_locked,false) THEN
        RAISE EXCEPTION 'sealed document index nodes are immutable';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER immutable_document_nodes BEFORE INSERT OR UPDATE OR DELETE ON artifacts.document_nodes FOR EACH ROW EXECUTE FUNCTION artifacts.guard_document_node()')
    op.execute("""CREATE FUNCTION artifacts.guard_document_index() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE actual_count bigint;
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'building' OR NEW.sealed THEN RAISE EXCEPTION 'document index must begin unsealed'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.sealed AND (to_jsonb(NEW) - ARRAY['status','publication_fencing_token']) IS DISTINCT FROM
                        (to_jsonb(OLD) - ARRAY['status','publication_fencing_token']) THEN
        RAISE EXCEPTION 'sealed document index is immutable';
      END IF;
      IF OLD.status = 'ready' AND NEW.status NOT IN ('ready','deletion_pending') THEN
        RAISE EXCEPTION 'ready document index cannot be rewritten';
      END IF;
      IF NEW.status = 'ready' AND OLD.status <> 'ready' THEN
        IF NOT NEW.sealed OR NEW.manifest_object_id IS NULL OR NEW.manifest_sha256 IS NULL OR NEW.root_node_id IS NULL THEN
          RAISE EXCEPTION 'ready index requires a sealed manifest and root';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM artifacts.processing_jobs WHERE id=NEW.job_id AND status='running'
                       AND fencing_token=NEW.publication_fencing_token AND lease_until > clock_timestamp()
                       AND recipe_fingerprint=NEW.recipe_fingerprint AND processing_fingerprint=NEW.processing_fingerprint
                       AND recipe->>'mode'='extract_index' AND recipe->'indexer'->>'name'=NEW.engine
                       AND recipe->'indexer'->>'version'=NEW.engine_version) THEN
          RAISE EXCEPTION 'document index requires its current live job fence and frozen engine';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM artifacts.representation_sets WHERE id=NEW.representation_set_id AND status='ready'
                       AND workspace_id=NEW.workspace_id AND artifact_id=NEW.artifact_id AND revision_id=NEW.revision_id
                       AND source_sha256=NEW.source_sha256 AND processing_fingerprint=NEW.processing_fingerprint
                       AND block_count=NEW.source_block_count AND coverage=NEW.coverage) THEN
          RAISE EXCEPTION 'document index requires its exact ready canonical generation';
        END IF;
        SELECT count(*) INTO actual_count FROM artifacts.document_nodes WHERE document_index_id=NEW.id;
        IF actual_count <> NEW.node_count OR actual_count < 1 THEN RAISE EXCEPTION 'document index node manifest is incomplete'; END IF;
        IF NOT EXISTS (SELECT 1 FROM artifacts.document_nodes WHERE id=NEW.root_node_id AND document_index_id=NEW.id
                       AND kind='root' AND parent_id IS NULL AND depth=0) THEN
          RAISE EXCEPTION 'document index root is invalid';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM artifacts.stored_objects WHERE id=NEW.manifest_object_id AND workspace_id=NEW.workspace_id
                       AND job_id=NEW.job_id AND state IN ('stored','referenced') AND role='document_index' AND sha256=NEW.manifest_sha256) THEN
          RAISE EXCEPTION 'document index manifest is unverified';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER immutable_document_index BEFORE INSERT OR UPDATE ON artifacts.document_indexes FOR EACH ROW EXECUTE FUNCTION artifacts.guard_document_index()')


def downgrade():
    op.execute('DROP TRIGGER immutable_document_nodes ON artifacts.document_nodes')
    op.execute('DROP TRIGGER immutable_document_index ON artifacts.document_indexes')
    op.execute('DROP FUNCTION artifacts.guard_document_node()')
    op.execute('DROP FUNCTION artifacts.guard_document_index()')
    op.drop_constraint('fk_artifact_document_index_root_node', 'document_indexes', schema='artifacts')
    op.drop_table('document_nodes', schema='artifacts')
    op.drop_table('document_indexes', schema='artifacts')
