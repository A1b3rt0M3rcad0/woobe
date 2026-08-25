from modules.agent.application.interfaces.runtime_environment import RuntimeEnvironmentGuard
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)


def build_agent_runtime_environment_guard(
    transactions: AgentRuntimeTransactionRunner,
) -> RuntimeEnvironmentGuard:
    async def guard(target_id, project_id, environment):
        async def assert_enabled(
            repositories: AgentRuntimeRepositories,
            _outbox,
        ) -> None:
            await repositories.environment.assert_enabled(
                agent_id=target_id,
                project_id=project_id,
                environment=environment,
            )

        await transactions.read(assert_enabled)

    return guard
