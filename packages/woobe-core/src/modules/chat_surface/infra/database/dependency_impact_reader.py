from sqlalchemy import select

from modules.chat_surface.infra.database.models import ChatSurfaceModel


class SurfaceDependencyImpactReader:
    def __init__(self, sessions):
        self._sessions = sessions

    async def consumers(self, *, project_id, agent_ids, release_ids, network_ids):
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ChatSurfaceModel).where(
                        ChatSurfaceModel.project_id == project_id,
                        ChatSurfaceModel.status != "archived",
                    )
                )
            ).all()
        return [
            {
                "type": "surface",
                "id": str(row.id),
                "name": row.name,
                "status": row.status,
                "field": "target_dependency",
            }
            for row in rows
            if (
                row.target_type == "agent"
                and (
                    str(row.target_id) in agent_ids
                    or str(row.target_release_id) in release_ids
                )
            )
            or (row.target_type == "network" and str(row.target_id) in network_ids)
        ]
