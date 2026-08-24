from modules.agent.application.interfaces.runtime_environment import RuntimeEnvironmentGuard
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)


def build_agent_runtime_environment_guard(
    transactions: AgentRuntimeTransactionRunner,
) -> RuntimeEnvironmentGuard:
    async def guard(target_id, project_id, environment):
        await transactions.assert_environment_enabled(
            target_id=target_id,
            project_id=project_id,
            environment=environment,
        )

    return guard
