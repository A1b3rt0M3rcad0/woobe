from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.application.interfaces.runtime_environment import RuntimeEnvironmentGuard
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.runtime_environment import assert_runtime_environment_enabled


def build_agent_runtime_environment_guard(engine: AsyncEngine) -> RuntimeEnvironmentGuard:
    async def guard(target_id, project_id, environment):
        async with AgentUnitOfWork(engine) as uow:
            await assert_runtime_environment_enabled(
                uow.session,
                target_type="agent",
                target_id=target_id,
                project_id=project_id,
                environment=environment,
            )

    return guard
