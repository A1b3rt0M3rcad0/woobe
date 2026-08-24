from __future__ import annotations

from typing import Any

from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from shared.runtime_environment import normalize_runtime_environment


class AgentRuntimeEnvironmentGuard:
    """Guards standalone Agent admission without owning persistence resources."""

    def __init__(
        self,
        delegate: Any,
        transactions: AgentRuntimeTransactionRunner,
        *,
        default_environment: str,
    ) -> None:
        self._delegate = delegate
        self._transactions = transactions
        self._default_environment = default_environment

    async def execute(self, input_dto: Any) -> Any:
        metadata = getattr(input_dto, "metadata", None)
        if isinstance(metadata, dict) and metadata.get("source") == "network_runtime":
            return await self._delegate.execute(input_dto)

        environment = normalize_runtime_environment(
            getattr(input_dto, "execution_context", None)
            or getattr(input_dto, "runtime_environment", None)
            or self._default_environment
        )
        await self._transactions.assert_environment_enabled(
            target_id=input_dto.agent_id,
            project_id=input_dto.project_id,
            environment=environment,
        )
        return await self._delegate.execute(input_dto)
