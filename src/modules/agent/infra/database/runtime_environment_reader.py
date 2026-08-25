from __future__ import annotations

from uuid import UUID

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.runtime_environment import assert_runtime_environment_enabled


class SQLAlchemyAgentRuntimeEnvironmentReader:
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def assert_enabled(
        self,
        *,
        agent_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> None:
        await assert_runtime_environment_enabled(
            self._uow.session,
            target_type="agent",
            target_id=agent_id,
            project_id=project_id,
            environment=environment,
        )
