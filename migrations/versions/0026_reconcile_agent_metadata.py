"""reconcile agent metadata with the consolidated schema

Revision ID: 0026
Revises: 0025
"""

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migration 0021 attempted to remove these cross-module constraints using
    # names that do not match every PostgreSQL-created constraint name.
    for table, names in (
        ("tools", ("tools_project_id_fkey", "tools_tools_project_id_fkey")),
        (
            "tool_secrets",
            (
                "secrets_project_id_fkey",
                "tool_secrets_project_id_fkey",
                "tools_secrets_project_id_fkey",
            ),
        ),
    ):
        for name in names:
            op.execute(
                f'ALTER TABLE agent."{table}" DROP CONSTRAINT IF EXISTS "{name}"'
            )

    # BaseModel declares timestamps as required. Backfill before tightening the
    # two legacy columns created nullable by migration 0006.
    op.execute(
        "UPDATE agent.ask_jobs SET created_at = now() WHERE created_at IS NULL"
    )
    op.execute(
        "UPDATE agent.ask_jobs SET updated_at = now() WHERE updated_at IS NULL"
    )
    op.alter_column(
        "ask_jobs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema="agent",
    )
    op.alter_column(
        "ask_jobs",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema="agent",
    )


def downgrade() -> None:
    op.alter_column(
        "ask_jobs",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema="agent",
    )
    op.alter_column(
        "ask_jobs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema="agent",
    )

    op.create_foreign_key(
        "tools_project_id_fkey",
        source_table="tools",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        source_schema="agent",
        referent_schema="core",
    )
    op.create_foreign_key(
        "secrets_project_id_fkey",
        source_table="tool_secrets",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        source_schema="agent",
        referent_schema="core",
    )
