from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.runtime_environment import (
    assert_runtime_environment_enabled,
    normalize_runtime_environment,
)


class AgentRuntimeEnvironmentGuard:
    """Guards standalone Agent admission without affecting Network invocations.

    Network execution invokes the Agent runtime in-process and identifies itself
    through metadata.source=network_runtime. Those invocations are governed by
    the Network environment switch and the explicit Agent snapshot selected by
    the Network version instead of the standalone Agent switch.
    """

    def __init__(
        self,
        delegate: Any,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        default_environment: str,
    ) -> None:
        self._delegate = delegate
        self._session_factory = session_factory
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
        async with self._session_factory() as session, session.begin():
            await assert_runtime_environment_enabled(
                session,
                target_type="agent",
                target_id=input_dto.agent_id,
                project_id=input_dto.project_id,
                environment=environment,
            )
        return await self._delegate.execute(input_dto)
