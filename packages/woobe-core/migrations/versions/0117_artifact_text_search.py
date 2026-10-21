"""Add bounded text search to immutable canonical source segments."""
from alembic import op
import sqlalchemy as sa

revision = '0117'
down_revision = '0116'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.add_column('workspaces', sa.Column('search_version', sa.BigInteger(), server_default='0', nullable=False), schema='artifacts')
    op.create_check_constraint('ck_artifact_workspace_search_version', 'workspaces', 'search_version >= 0', schema='artifacts')
    op.add_column('representation_sets', sa.Column('published_search_version', sa.BigInteger(), nullable=True), schema='artifacts')
    op.execute("UPDATE artifacts.representation_sets SET published_search_version=0 WHERE status='ready'")
    op.create_check_constraint('ck_artifact_representation_search_version', 'representation_sets',
        "status <> 'ready' OR published_search_version IS NOT NULL", schema='artifacts')
    op.execute('DROP TRIGGER immutable_representation_set ON artifacts.representation_sets')
    op.execute('DROP FUNCTION artifacts.guard_representation_set()')
    op.execute("""CREATE FUNCTION artifacts.guard_representation_set() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE actual_count bigint; source_hash text; job_recipe text;
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'building' OR NEW.sealed THEN RAISE EXCEPTION 'representation must begin unsealed'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.sealed AND (to_jsonb(NEW) - ARRAY['status','publication_fencing_token','published_search_version']) IS DISTINCT FROM
                        (to_jsonb(OLD) - ARRAY['status','publication_fencing_token','published_search_version']) THEN
        RAISE EXCEPTION 'sealed representation set is immutable';
      END IF;
      IF OLD.status = 'ready' AND NEW.status NOT IN ('ready','deletion_pending') THEN
        RAISE EXCEPTION 'ready representation cannot be rewritten';
      END IF;
      IF OLD.status = 'ready' AND NEW.published_search_version IS DISTINCT FROM OLD.published_search_version THEN
        RAISE EXCEPTION 'published search version is immutable';
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
    op.add_column('source_segments', sa.Column('search_text', sa.Text(), nullable=False,
        server_default=sa.text("''")), schema='artifacts')
    op.alter_column('source_segments', 'search_text', server_default=None, schema='artifacts')
    op.add_column('source_segments', sa.Column('search_normalized', sa.Text(), nullable=False,
        server_default=sa.text("''")), schema='artifacts')
    op.execute('UPDATE artifacts.source_segments SET search_normalized=normalize(search_text, NFKC)')
    op.alter_column('source_segments', 'search_normalized', server_default=None, schema='artifacts')
    op.add_column('source_segments', sa.Column('search_vector', sa.dialects.postgresql.TSVECTOR(),
        sa.Computed("to_tsvector('simple'::regconfig, search_normalized)", persisted=True), nullable=True), schema='artifacts')
    op.create_index('ix_artifact_source_segment_search_vector', 'source_segments', ['search_vector'],
        schema='artifacts', postgresql_using='gin')
    op.create_index('ix_artifact_source_segment_search_literal', 'source_segments', ['search_normalized'],
        schema='artifacts', postgresql_using='gin', postgresql_ops={'search_normalized': 'gin_trgm_ops'})
    op.create_index('ix_artifact_history_search_path', 'head_history', [
        sa.text("to_tsvector('simple'::regconfig, normalize(regexp_replace(path, '[^[:alnum:]]+', ' ', 'g'), NFKC))")],
        schema='artifacts', postgresql_using='gin')
    op.create_index('ix_artifact_history_search_path_literal', 'head_history', ['path'],
        schema='artifacts', postgresql_using='gin', postgresql_ops={'path': 'gin_trgm_ops'})


def downgrade():
    op.drop_index('ix_artifact_history_search_path_literal', table_name='head_history', schema='artifacts')
    op.drop_index('ix_artifact_history_search_path', table_name='head_history', schema='artifacts')
    op.drop_index('ix_artifact_source_segment_search_literal', table_name='source_segments', schema='artifacts')
    op.drop_index('ix_artifact_source_segment_search_vector', table_name='source_segments', schema='artifacts')
    op.drop_column('source_segments', 'search_vector', schema='artifacts')
    op.drop_column('source_segments', 'search_normalized', schema='artifacts')
    op.drop_column('source_segments', 'search_text', schema='artifacts')
    op.drop_constraint('ck_artifact_representation_search_version', 'representation_sets', schema='artifacts')
    op.drop_column('representation_sets', 'published_search_version', schema='artifacts')
    op.drop_constraint('ck_artifact_workspace_search_version', 'workspaces', schema='artifacts')
    op.drop_column('workspaces', 'search_version', schema='artifacts')
