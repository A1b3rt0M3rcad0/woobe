from __future__ import annotations

from uuid import UUID

from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from shared.contracts.errors import AuthorizationError, NotFoundError
from shared.security.principal import AuthenticatedPrincipal


class AgentRunContextReadService:
    """Control-plane read model for per-invocation Context evidence."""

    def __init__(self, transactions: AgentRuntimeTransactionRunner) -> None:
        self._transactions = transactions

    async def list_model_invocations(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> list[dict]:
        async def read(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.get_by_id(run_id)
            if run is None:
                raise NotFoundError("Agent Run not found")
            if not isinstance(principal, AuthenticatedPrincipal):
                # Context manifests may contain internal Knowledge/Tool provenance.
                # Runtime keys and public surfaces do not receive this control-plane view.
                raise AuthorizationError("Control-plane authentication required")
            await repositories.project_access.require_user_access(
                user_id=principal.user_id,
                project_id=run.project_id,
            )
            return await repositories.runs.list_model_invocations(run_id)

        return await self._transactions.read(read)
