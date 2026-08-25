from uuid import UUID

from sqlalchemy import text

from modules.core.domain.enums import RuntimeTargetType
from shared.infra.config.interface.unit_of_work import UnitOfWork


class RuntimeKeyTargetReader:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def get_target_project_id(
        self,
        target_type: RuntimeTargetType,
        target_id: UUID,
    ) -> UUID | None:
        if target_type == RuntimeTargetType.agent:
            statement = """
                SELECT project_id
                FROM agent.agents
                WHERE id = :target_id
                  AND status = 'active'
            """
        elif target_type == RuntimeTargetType.network:
            statement = """
                SELECT project_id
                FROM network.networks
                WHERE id = :target_id
            """
        else:
            return None

        result = await self._uow.session.execute(
            text(statement),
            {"target_id": target_id},
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def get_agent_project_id(self, agent_id: UUID) -> UUID | None:
        return await self.get_target_project_id(RuntimeTargetType.agent, agent_id)
