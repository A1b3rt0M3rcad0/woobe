"""Permit only recipe-authorized structural indexer fallback at publication."""
from alembic import op
import sqlalchemy as sa

revision = '0116'
down_revision = '0115'
branch_labels = None
depends_on = None


def _install_guard(*, allow_fallback):
    engine_policy = ("((recipe->'indexer'->>'name'=NEW.engine "
        "AND recipe->'indexer'->>'version'=NEW.engine_version) "
        "OR (NEW.engine='structural' AND NEW.engine_version='1' "
        "AND recipe->'parameters'->>'indexer_fallback'='structural'))"
        if allow_fallback else
        "(recipe->'indexer'->>'name'=NEW.engine "
        "AND recipe->'indexer'->>'version'=NEW.engine_version)")
    op.execute("DROP TRIGGER immutable_document_index ON artifacts.document_indexes")
    op.execute("DROP FUNCTION artifacts.guard_document_index()")
    op.execute(f"""CREATE FUNCTION artifacts.guard_document_index() RETURNS trigger LANGUAGE plpgsql AS $$
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
                       AND recipe->>'mode'='extract_index' AND {engine_policy}) THEN
          RAISE EXCEPTION 'document index requires its current live job fence and authorized engine';
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


def upgrade():
    # Keep the frozen source indexer in the recipe and record the actual engine
    # on the published index. Structural fallback is valid only when the caller
    # opted into it in that immutable recipe.
    _install_guard(allow_fallback=True)


def downgrade():
    fallback_index_exists = op.get_bind().scalar(sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM artifacts.document_indexes AS idx
          JOIN artifacts.processing_jobs AS job ON job.id=idx.job_id
          WHERE idx.engine='structural' AND idx.engine_version='1'
            AND NOT (job.recipe->'indexer'->>'name'='structural'
                     AND job.recipe->'indexer'->>'version'='1')
        )
    """))
    if fallback_index_exists:
        raise RuntimeError('Published structural fallback indexes must be retained')
    _install_guard(allow_fallback=False)
