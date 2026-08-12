"""bind ChatSurfaces and Sessions to immutable releases

Revision ID: 0059
Revises: 0058
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def _require_complete_backfill(table: str) -> None:
    connection = op.get_bind()
    missing = connection.execute(
        sa.text(
            f"SELECT count(*) FROM chat_surface.{table} "
            "WHERE target_release_id IS NULL"
        )
    ).scalar_one()
    if int(missing or 0) > 0:
        raise RuntimeError(
            f"Cannot bind {table} to immutable releases: {missing} rows have no release"
        )


def upgrade() -> None:
    op.add_column(
        "chat_surfaces",
        sa.Column("target_release_id", sa.Uuid(), nullable=True),
        schema="chat_surface",
    )
    op.add_column(
        "session_bindings",
        sa.Column("target_release_id", sa.Uuid(), nullable=True),
        schema="chat_surface",
    )

    op.execute(
        """
        UPDATE chat_surface.chat_surfaces AS surface
        SET target_release_id = COALESCE(
            (
                SELECT activation.release_id
                FROM agent.agent_release_activations AS activation
                WHERE activation.project_id = surface.project_id
                  AND activation.agent_id = surface.target_id
                ORDER BY activation.created_at DESC, activation.id DESC
                LIMIT 1
            ),
            (
                SELECT release.id
                FROM agent.agent_releases AS release
                WHERE release.project_id = surface.project_id
                  AND release.agent_id = surface.target_id
                  AND release.status = 'production'
                ORDER BY release.updated_at DESC, release.created_at DESC, release.id DESC
                LIMIT 1
            )
        )
        WHERE surface.target_type = 'agent'
          AND surface.target_release_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE chat_surface.chat_surfaces AS surface
        SET target_release_id = network.production_version_id
        FROM network.networks AS network
        WHERE surface.target_type = 'network'
          AND surface.project_id = network.project_id
          AND surface.target_id = network.id
          AND surface.target_release_id IS NULL
        """
    )
    _require_complete_backfill("chat_surfaces")

    op.execute(
        """
        UPDATE chat_surface.session_bindings AS binding
        SET target_release_id = session.opened_release_id
        FROM agent.sessions AS session
        WHERE binding.target_type = 'agent'
          AND binding.session_id = session.id
          AND binding.target_release_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE chat_surface.session_bindings AS binding
        SET target_release_id = session.network_version_id
        FROM network.network_sessions AS session
        WHERE binding.target_type = 'network'
          AND binding.session_id = session.id
          AND binding.target_release_id IS NULL
        """
    )
    _require_complete_backfill("session_bindings")

    op.execute(
        """
        UPDATE agent.sessions
        SET data = (
            COALESCE(data, '{}'::jsonb)
            - 'chat_surface_dynamic_release'
        ) || jsonb_build_object(
            'source', 'chat_surface',
            'runtime_environment', 'production',
            'loaded_release_id', opened_release_id::text
        )
        WHERE chat_surface_id IS NOT NULL
          AND opened_release_id IS NOT NULL
        """
    )

    op.alter_column(
        "chat_surfaces",
        "target_release_id",
        nullable=False,
        schema="chat_surface",
    )
    op.alter_column(
        "session_bindings",
        "target_release_id",
        nullable=False,
        schema="chat_surface",
    )

    op.create_index(
        "ix_chat_surface_release",
        "chat_surfaces",
        ["project_id", "target_type", "target_release_id", "status"],
        schema="chat_surface",
    )
    op.create_index(
        "ix_chat_surface_session_release",
        "session_bindings",
        ["target_type", "target_release_id", "status"],
        schema="chat_surface",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_surface_session_release",
        table_name="session_bindings",
        schema="chat_surface",
    )
    op.drop_index(
        "ix_chat_surface_release",
        table_name="chat_surfaces",
        schema="chat_surface",
    )
    op.drop_column(
        "session_bindings",
        "target_release_id",
        schema="chat_surface",
    )
    op.drop_column(
        "chat_surfaces",
        "target_release_id",
        schema="chat_surface",
    )
