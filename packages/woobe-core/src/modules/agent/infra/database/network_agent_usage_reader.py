from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text, select
from modules.agent.infra.database.models import AgentReleaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class SessionProvider(Protocol):
    @property
    def session(self) -> AsyncSession: ...


class SQLAlchemyNetworkAgentUsageReader:
    """Read Network Draft references using the active Agent unit of work."""

    def __init__(self, session_provider: SessionProvider, network_consumers=None, surface_consumers=None) -> None:
        self._session_provider = session_provider
        self._network_consumers, self._surface_consumers = network_consumers, surface_consumers

    async def list_draft_references(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
    ) -> list[dict[str, str]]:
        if self._network_consumers is not None and self._surface_consumers is not None:
            releases = (await self._session_provider.session.scalars(
                select(AgentReleaseModel.id).where(AgentReleaseModel.project_id == project_id, AgentReleaseModel.agent_id == agent_id)
            )).all()
            agent_ids, release_ids = {str(agent_id)}, {str(item) for item in releases}
            networks = await self._network_consumers(project_id=project_id, agent_ids=agent_ids, release_ids=release_ids)
            surfaces = await self._surface_consumers(project_id=project_id, agent_ids=agent_ids, release_ids=release_ids, network_ids={item["id"] for item in networks})
            return [*networks, *surfaces]
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
