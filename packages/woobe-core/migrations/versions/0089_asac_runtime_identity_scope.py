"""Versioned runtime scopes preserve historical Candidate hashes unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def _guard(owner, fields):
    op.execute(f"""CREATE OR REPLACE FUNCTION {owner}.guard_asac_ready_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' OR (OLD.state IN ('ready','rejected') AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)) THEN
            RAISE EXCEPTION 'Sealed ASaC Candidate evidence cannot be modified or deleted';
        END IF;
        IF (to_jsonb(NEW) - ARRAY[{fields}]) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY[{fields}]) THEN
            RAISE EXCEPTION 'Accepted ASaC Candidate identity is immutable';
        END IF;
        RETURN NEW;
    END $$""")


_BASE_FIELDS = "'state','root_snapshot_id','runtime_digest','native_bindings','runtime_fingerprints','updated_at'"


def upgrade():
    for owner in ("agent", "network"):
        op.add_column("asac_candidates", sa.Column("runtime_digest_scope", sa.String(64), nullable=True), schema=owner)
        _guard(owner, _BASE_FIELDS + ",'runtime_digest_scope'")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM agent.asac_candidates WHERE runtime_digest_scope IS NOT NULL)
        OR EXISTS (SELECT 1 FROM network.asac_candidates WHERE runtime_digest_scope IS NOT NULL)
        THEN RAISE EXCEPTION 'Retained Candidate runtime scope prevents destructive downgrade'; END IF;
    END $$""")
    for owner in ("network", "agent"):
        _guard(owner, _BASE_FIELDS)
        op.drop_column("asac_candidates", "runtime_digest_scope", schema=owner)
