"""Keep policy event content immutable while permitting outbox delivery metadata."""
from alembic import op

revision='0096'
down_revision='0095'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""CREATE OR REPLACE FUNCTION core.guard_asac_policy_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF EXISTS(SELECT 1 FROM core.asac_project_lifecycle_operations WHERE outbox_id=OLD.id) THEN
          IF TG_OP='DELETE' OR
            (to_jsonb(NEW)-ARRAY['status','attempts','error','published_at','updated_at','locked_at','locked_by','available_at'])
            IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','attempts','error','published_at','updated_at','locked_at','locked_by','available_at'])
          THEN RAISE EXCEPTION 'ASAC_PROJECT_POLICY_IMMUTABLE'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")


def downgrade():
    raise RuntimeError('Reverting would block policy outbox delivery; use a forward migration')
