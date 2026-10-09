"""Keep accepted evaluation identity and terminal evidence immutable in SQL."""
from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade():
    for owner in ("agent", "network"):
        op.execute(f"""CREATE FUNCTION {owner}.guard_asac_evaluation_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Retained ASaC evaluation evidence cannot be deleted';
            END IF;
            IF OLD.state IN ('passed', 'failed', 'uncertain') AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
                RAISE EXCEPTION 'Terminal ASaC evaluation evidence is immutable';
            END IF;
            IF (to_jsonb(NEW) - ARRAY['state', 'cases', 'error_code', 'updated_at'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['state', 'cases', 'error_code', 'updated_at']) THEN
                RAISE EXCEPTION 'Accepted ASaC evaluation identity is immutable';
            END IF;
            IF OLD.state = 'running' AND NEW.state = 'accepted' THEN
                RAISE EXCEPTION 'ASaC evaluation cannot return to accepted';
            END IF;
            IF jsonb_array_length(NEW.cases::jsonb) <> jsonb_array_length(OLD.cases::jsonb)
                OR EXISTS (SELECT 1 FROM jsonb_array_elements(OLD.cases::jsonb) WITH ORDINALITY old_case(value, ordinal)
                JOIN jsonb_array_elements(NEW.cases::jsonb) WITH ORDINALITY new_case(value, ordinal) USING (ordinal)
                WHERE old_case.value->'id' IS DISTINCT FROM new_case.value->'id'
                   OR old_case.value->'run_id' IS DISTINCT FROM new_case.value->'run_id') THEN
                RAISE EXCEPTION 'Accepted ASaC case execution identity is immutable';
            END IF;
            RETURN NEW;
        END $$""")
        op.execute(f"""CREATE TRIGGER guard_asac_evaluation_evidence BEFORE UPDATE OR DELETE
            ON {owner}.asac_evaluations FOR EACH ROW EXECUTE FUNCTION {owner}.guard_asac_evaluation_evidence()""")


def downgrade():
    for owner in ("network", "agent"):
        op.execute(f"DROP TRIGGER guard_asac_evaluation_evidence ON {owner}.asac_evaluations")
        op.execute(f"DROP FUNCTION {owner}.guard_asac_evaluation_evidence()")
