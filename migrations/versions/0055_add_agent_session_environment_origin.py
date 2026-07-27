"""persist Agent Session environment and opening Release provenance

Revision ID: 0055
Revises: 0054
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

_UUID_RE = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("runtime_environment", sa.String(length=16), nullable=True),
        schema="agent",
    )
    op.add_column(
        "sessions",
        sa.Column("opened_release_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="agent",
    )

    # Sessions created before runtime environments existed were Draft Sessions.
    # Sessions created by the first environment-aware Playground implementation
    # stored this information inside JSONB; migrate that metadata into explicit
    # operational columns without trusting malformed or non-object JSON values.
    op.execute(
        """
        UPDATE agent.sessions
        SET runtime_environment = CASE
            WHEN jsonb_typeof(data) = 'object'
             AND data ->> 'runtime_environment' IN ('draft', 'staging', 'production')
                THEN data ->> 'runtime_environment'
            ELSE 'draft'
        END
        """
    )
    op.execute(
        f"""
        UPDATE agent.sessions AS session
        SET opened_release_id = (session.data ->> 'loaded_release_id')::uuid
        WHERE jsonb_typeof(session.data) = 'object'
          AND session.data ->> 'loaded_release_id' ~* '{_UUID_RE}'
          AND EXISTS (
              SELECT 1
              FROM agent.agent_releases AS release
              WHERE release.id = (session.data ->> 'loaded_release_id')::uuid
                AND release.agent_id = session.agent_id
                AND release.project_id = session.project_id
          )
        """
    )
    op.execute(
        """
        UPDATE agent.sessions
        SET data = NULLIF(
            data - 'runtime_environment' - 'loaded_release_id' - 'release_version',
            '{}'::jsonb
        )
        WHERE jsonb_typeof(data) = 'object'
        """
    )

    op.alter_column(
        "sessions",
        "runtime_environment",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default=sa.text("'draft'"),
        schema="agent",
    )
    op.create_check_constraint(
        "ck_agent_sessions_runtime_environment",
        "sessions",
        "runtime_environment IN ('draft', 'staging', 'production')",
        schema="agent",
    )
    op.create_foreign_key(
        "fk_agent_sessions_opened_release",
        "sessions",
        "agent_releases",
        ["opened_release_id"],
        ["id"],
        source_schema="agent",
        referent_schema="agent",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_agent_sessions_environment_activity",
        "sessions",
        ["project_id", "agent_id", "runtime_environment", "last_message_at", "id"],
        schema="agent",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_sessions_environment_activity",
        table_name="sessions",
        schema="agent",
    )
    op.drop_constraint(
        "fk_agent_sessions_opened_release",
        "sessions",
        schema="agent",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_agent_sessions_runtime_environment",
        "sessions",
        schema="agent",
        type_="check",
    )
    op.drop_column("sessions", "opened_release_id", schema="agent")
    op.drop_column("sessions", "runtime_environment", schema="agent")
