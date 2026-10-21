"""Allow only the retention lifecycle to make immutable revisions unavailable.

Revision ID: 0125
Revises: 0124
"""

from alembic import op


revision = "0125"
down_revision = "0124"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TRIGGER artifact_revision_immutable ON artifacts.revisions")
    op.execute("""
        CREATE OR REPLACE FUNCTION artifacts.reject_revision_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'content_state' - 'source_refs' - 'external_operation_ref')
                IS DISTINCT FROM
               (to_jsonb(OLD) - 'content_state' - 'source_refs' - 'external_operation_ref') THEN
                RAISE EXCEPTION 'Artifact revision data is immutable';
            END IF;

            IF NOT (
                (OLD.content_state = 'available' AND NEW.content_state = 'deletion_pending')
                OR (OLD.content_state = 'deletion_pending' AND NEW.content_state = 'purged')
            ) THEN
                RAISE EXCEPTION 'Invalid Artifact revision lifecycle transition';
            END IF;

            IF NEW.content_state <> 'purged'
               AND (NEW.source_refs IS DISTINCT FROM OLD.source_refs
                    OR NEW.external_operation_ref IS DISTINCT FROM OLD.external_operation_ref) THEN
                RAISE EXCEPTION 'Artifact revision provenance can only be scrubbed on purge';
            END IF;

            IF NEW.content_state = 'purged'
               AND (NEW.source_refs <> '[]'::jsonb OR NEW.external_operation_ref IS NOT NULL) THEN
                RAISE EXCEPTION 'Purged Artifact revision provenance must be scrubbed';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER artifact_revision_immutable BEFORE UPDATE ON artifacts.revisions "
        "FOR EACH ROW EXECUTE FUNCTION artifacts.reject_revision_update()"
    )


def downgrade():
    op.execute("DROP TRIGGER artifact_revision_immutable ON artifacts.revisions")
    op.execute("""
        CREATE OR REPLACE FUNCTION artifacts.reject_revision_update()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'Artifact revisions are immutable';
        END $$
    """)
    op.execute(
        "CREATE TRIGGER artifact_revision_immutable BEFORE UPDATE ON artifacts.revisions "
        "FOR EACH ROW EXECUTE FUNCTION artifacts.reject_revision_update()"
    )
