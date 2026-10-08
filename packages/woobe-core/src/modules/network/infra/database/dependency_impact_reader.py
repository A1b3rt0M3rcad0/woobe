from sqlalchemy import select

from modules.network.infra.database.models import NetworkModel, NetworkVersionModel


class NetworkDependencyImpactReader:
    def __init__(self, sessions):
        self._sessions = sessions

    async def consumers(self, *, project_id, agent_ids, release_ids):
        async with self._sessions() as session:
            networks = (
                await session.scalars(
                    select(NetworkModel).where(NetworkModel.project_id == project_id)
                )
            ).all()
            versions = (
                await session.scalars(
                    select(NetworkVersionModel).where(
                        NetworkVersionModel.project_id == project_id
                    )
                )
            ).all()
        impacted = set()
        for network in networks:
            if any(
                str(node.get("agent_id")) in agent_ids
                for node in (network.draft_definition or {}).get("nodes", [])
            ):
                impacted.add(network.id)
        for version in versions:
            if any(
                str(binding.get("release_id")) in release_ids
                or str(binding.get("agent_id")) in agent_ids
                for binding in (version.resolved_bindings or {}).values()
            ):
                impacted.add(version.network_id)
        return [
            {
                "type": "network",
                "id": str(row.id),
                "name": row.name,
                "status": "active",
                "field": "agent_dependency",
            }
            for row in networks
            if row.id in impacted
        ]
