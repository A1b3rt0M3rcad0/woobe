"""Versioned Project Skill packages.

Revision ID: 0064
Revises: 0063
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "name", name="uq_agent_skills_project_name"),
        schema="agent",
    )
    op.create_index(
        "ix_agent_skills_project_id", "skills", ["project_id"], schema="agent"
    )
    op.create_table(
        "skill_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "skill_id",
            sa.Uuid(),
            sa.ForeignKey("agent.skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("package", postgresql.JSONB(), nullable=False),
        sa.Column("package_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "skill_id", "version", name="uq_agent_skill_versions_version"
        ),
        schema="agent",
    )
    op.create_index(
        "ix_agent_skill_versions_skill_created",
        "skill_versions",
        ["skill_id", "created_at"],
        schema="agent",
    )


def downgrade() -> None:
    op.drop_table("skill_versions", schema="agent")
    op.drop_table("skills", schema="agent")
