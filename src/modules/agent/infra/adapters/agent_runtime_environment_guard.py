from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.runtime_environment import (
    assert_runtime_environment_enabled,
    normalize_runtime_environment,
)


class AgentRuntimeEnvironmentGuard:
    """Guards standalone Agent admission without affecting Network invocations."""

    def __init__(
        self,
        delegate: Any,
        engine: AsyncEngine,
        *,
        default_environment: str,
    ) -> None:
        self._delegate = delegate
        self._engine = engine
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
        async with AgentUnitOfWork(self._engine) as uow:
            await assert_runtime_environment_enabled(
                uow.session,
                target_type="agent",
                target_id=input_dto.agent_id,
                project_id=input_dto.project_id,
                environment=environment,
            )
        return await self._delegate.execute(input_dto)
