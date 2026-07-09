from uuid import UUID

from sqlalchemy import text

from shared.infra.config.interface.unit_of_work import UnitOfWork


class RuntimeKeyTargetReader:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def get_agent_project_id(self, agent_id: UUID) -> UUID | None:
        result = await self._uow.session.execute(
            text(
                """
                SELECT project_id
                FROM agent.agents
                WHERE id = :agent_id
                  AND status = 'active'
                """
            ),
            {"agent_id": agent_id},
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None
