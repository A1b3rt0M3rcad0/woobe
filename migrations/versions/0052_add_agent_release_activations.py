"""add agent release activation history

Revision ID: 0052
Revises: 0051
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

_ACTION_CHECK = "action IN ('deploy', 'reactivate', 'rollback')"


def upgrade() -> None:
    op.create_table(
        "agent_release_activations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "release_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.agent_releases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "previous_release_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.agent_releases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint(_ACTION_CHECK, name="ck_agent_release_activations_action"),
        schema="agent",
    )
    op.create_index(
        "ix_agent_release_activations_agent_created_at",
        "agent_release_activations",
        ["agent_id", "created_at"],
        unique=False,
        schema="agent",
    )

    # Existing Production snapshots become the first known deployment event.
    op.execute(
        """
        INSERT INTO agent.agent_release_activations
            (id, project_id, agent_id, release_id, previous_release_id, action,
             created_by, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            release.project_id,
            release.agent_id,
            release.id,
            NULL,
            'deploy',
            release.promoted_by,
            COALESCE(release.promoted_at, release.created_at, now()),
            COALESCE(release.promoted_at, release.updated_at, release.created_at, now())
        FROM agent.agent_releases AS release
        WHERE release.status = 'production'
          AND release.snapshot_kind = 'release'
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_release_activations_agent_created_at",
        table_name="agent_release_activations",
        schema="agent",
    )
    op.drop_table("agent_release_activations", schema="agent")
