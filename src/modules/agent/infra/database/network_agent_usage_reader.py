from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SessionProvider(Protocol):
    @property
    def session(self) -> AsyncSession: ...


class SQLAlchemyNetworkAgentUsageReader:
    """Read Network Draft references using the active Agent unit of work."""

    def __init__(self, session_provider: SessionProvider) -> None:
        self._session_provider = session_provider

    async def list_draft_references(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
    ) -> list[dict[str, str]]:
        result = await self._session_provider.session.execute(
            text(
                """
                SELECT network.id, network.name
                FROM network.networks AS network
                WHERE network.project_id = :project_id
                  AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(
                      COALESCE(network.draft_definition -> 'nodes', '[]'::jsonb)
                    ) AS node
                    WHERE node ->> 'agent_id' = :agent_id
                  )
                ORDER BY network.name, network.id
                """
            ),
            {"project_id": project_id, "agent_id": str(agent_id)},
        )
        return [
            {"id": str(row.id), "name": str(row.name)}
            for row in result.all()
        ]
