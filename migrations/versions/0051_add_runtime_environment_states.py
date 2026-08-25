"""add runtime environment states

Revision ID: 0051
Revises: 0050
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None

_ENVIRONMENT_CHECK = "environment IN ('draft', 'staging', 'production')"
_SESSION_MODE_CHECK = "session_mode IN ('stateful', 'stateless')"


def _create_runtime_state_table(*, schema: str, table: str, target_table: str, target_column: str) -> None:
    op.create_table(
        table,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            target_column,
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{schema}.{target_table}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(_ENVIRONMENT_CHECK, name=f"ck_{table}_environment"),
        sa.UniqueConstraint(target_column, "environment", name=f"uq_{table}_target_environment"),
        schema=schema,
    )
    op.create_index(
        f"ix_{table}_project_environment",
        table,
        ["project_id", "environment"],
        unique=False,
        schema=schema,
    )


def upgrade() -> None:
    _create_runtime_state_table(
        schema="agent",
        table="agent_runtime_environment_states",
        target_table="agents",
        target_column="agent_id",
    )
    _create_runtime_state_table(
        schema="network",
        table="network_runtime_environment_states",
        target_table="networks",
        target_column="network_id",
    )

    op.execute(
        """
        INSERT INTO agent.agent_runtime_environment_states
            (id, project_id, agent_id, environment, enabled, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            agent.project_id,
            agent.id,
            environment.name,
            CASE WHEN agent.status = 'inactive' THEN false ELSE true END,
            now(),
            now()
        FROM agent.agents AS agent
        CROSS JOIN (VALUES ('draft'), ('staging'), ('production')) AS environment(name)
        ON CONFLICT (agent_id, environment) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO network.network_runtime_environment_states
            (id, project_id, network_id, environment, enabled, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            network.project_id,
            network.id,
            environment.name,
            true,
            now(),
            now()
        FROM network.networks AS network
        CROSS JOIN (VALUES ('draft'), ('staging'), ('production')) AS environment(name)
        ON CONFLICT (network_id, environment) DO NOTHING
        """
    )

    # Runtime availability now lives in the environment-state table. Keep the
    # legacy Agent row active so immutable Agent snapshots used by Networks are
    # not blocked by a standalone operational switch.
    op.execute("UPDATE agent.agents SET status = 'active' WHERE status = 'inactive'")

    # Legacy releases inherited the mutable Agent field. Freeze the currently
    # effective value so future changes cannot alter historical snapshots.
    op.execute(
        """
        UPDATE agent.agent_releases AS release
        SET session_mode = agent.session_mode
        FROM agent.agents AS agent
        WHERE release.agent_id = agent.id
          AND release.session_mode IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM agent.agent_releases
                WHERE session_mode IS NULL
                   OR session_mode NOT IN ('stateful', 'stateless')
            ) THEN
                RAISE EXCEPTION 'Agent release session_mode backfill is incomplete or invalid';
            END IF;
        END $$;
        """
    )
    op.alter_column(
        "agent_releases",
        "session_mode",
        existing_type=sa.String(length=32),
        nullable=False,
        schema="agent",
    )
    op.create_check_constraint(
        "ck_agent_releases_session_mode",
        "agent_releases",
        _SESSION_MODE_CHECK,
        schema="agent",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_releases_session_mode",
        "agent_releases",
        schema="agent",
        type_="check",
    )
    op.alter_column(
        "agent_releases",
        "session_mode",
        existing_type=sa.String(length=32),
        nullable=True,
        schema="agent",
    )
    op.drop_index(
        "ix_network_runtime_environment_states_project_environment",
        table_name="network_runtime_environment_states",
        schema="network",
    )
    op.drop_table("network_runtime_environment_states", schema="network")
    op.drop_index(
        "ix_agent_runtime_environment_states_project_environment",
        table_name="agent_runtime_environment_states",
        schema="agent",
    )
    op.drop_table("agent_runtime_environment_states", schema="agent")
