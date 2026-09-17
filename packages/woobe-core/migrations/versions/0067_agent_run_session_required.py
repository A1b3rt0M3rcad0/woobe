"""Backfill isolated Sessions for legacy Runs, then require Session identity.

Revision ID: 0067
Revises: 0066
"""

from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lock writers while assigning IDs so a concurrent legacy writer cannot add
    # another NULL between the backfill and the constraint. No existing Session
    # or Run is deleted or merged. The temporary mapping is transaction scoped.
    op.execute("LOCK TABLE agent.agent_runs IN SHARE ROW EXCLUSIVE MODE")
    op.execute("""
        CREATE TEMP TABLE agent_run_session_backfill ON COMMIT DROP AS
        SELECT id AS run_id, gen_random_uuid() AS session_id
        FROM agent.agent_runs WHERE session_id IS NULL
    """)
    op.execute("""
        INSERT INTO agent.sessions (
            id, project_id, agent_id, runtime_environment, opened_release_id,
            origin, status, mode, data, created_at, updated_at
        )
        SELECT b.session_id, r.project_id, r.agent_id,
               CASE WHEN r.environment IN ('draft', 'staging', 'production')
                    THEN r.environment WHEN r.environment = 'release'
                    THEN 'production' ELSE 'draft' END,
               r.agent_release_id, left(r.origin, 32), 'active', 'chat',
               jsonb_build_object('legacy_run_id', r.id::text,
                                  'source', r.origin,
                                  'legacy_environment', r.environment,
                                  'session_backfill', '0067'),
               r.created_at, r.updated_at
        FROM agent.agent_runs r
        JOIN agent_run_session_backfill b ON b.run_id = r.id
    """)
    op.execute("""
        UPDATE agent.agent_runs r SET session_id = b.session_id
        FROM agent_run_session_backfill b WHERE r.id = b.run_id
    """)
    op.alter_column("agent_runs", "session_id", schema="agent",
                    existing_type=sa.Uuid(), nullable=False)


def downgrade() -> None:
    # Preserve historical identity even when rolling back the constraint.
    op.alter_column("agent_runs", "session_id", schema="agent",
                    existing_type=sa.Uuid(), nullable=True)
