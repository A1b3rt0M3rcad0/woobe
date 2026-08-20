from modules.agent.application.interfaces.runtime_environment import RuntimeEnvironmentGuard
from shared.runtime_environment import assert_runtime_environment_enabled


def build_agent_runtime_environment_guard(session_factory) -> RuntimeEnvironmentGuard:
    async def guard(target_id, project_id, environment):
        async with session_factory() as session, session.begin():
            await assert_runtime_environment_enabled(
                session,
                target_type="agent",
                target_id=target_id,
                project_id=project_id,
                environment=environment,
            )
    return guard
