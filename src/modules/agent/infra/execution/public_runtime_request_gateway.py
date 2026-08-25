from __future__ import annotations

from uuid import UUID

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.use_cases.public_runtime_request_preparer import (
    PublicRuntimeRequestPreparer,
)
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)


class PublicRuntimeRequestGateway:
    """Prepares public runtime requests inside a short database transaction."""

    def __init__(self, transactions: AgentRuntimeTransactionRunner) -> None:
        self._transactions = transactions

    async def prepare(
        self,
        payload: PublicRunRequest,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
    ) -> PublicRunRequest:
        async def prepare_request(
            repositories: AgentRuntimeRepositories,
            _outbox,
        ) -> PublicRunRequest:
            preparer = PublicRuntimeRequestPreparer(
                repositories.releases,
                repositories.sessions,
                repositories.agents,
            )
            return await preparer.prepare(
                payload,
                project_id=project_id,
                agent_id=agent_id,
                environment=environment,
            )

        return await self._transactions.run(prepare_request)
