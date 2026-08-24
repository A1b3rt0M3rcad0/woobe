from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.runtime_repositories import (
    AgentRuntimeRepositories,
    build_agent_runtime_repositories,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.runtime_environment import assert_runtime_environment_enabled


ResultT = TypeVar("ResultT")
UnitOfWorkFactory = Callable[[], AgentUnitOfWork]
RuntimeTransactionOperation = Callable[
    [AgentRuntimeRepositories, OutboxEventWriter],
    Awaitable[ResultT],
]


class AgentRuntimeTransactionRunner:
    """Runs short Agent persistence phases behind an explicit UoW boundary.

    Long-lived Agent execution receives this boundary instead of an Engine,
    AsyncSession or UnitOfWork. A fresh UoW is created for every persistence
    phase, so provider/tool latency never keeps a database transaction open.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def run(
        self,
        operation: RuntimeTransactionOperation[ResultT],
    ) -> ResultT:
        async with self._uow_factory() as uow:
            repositories = build_agent_runtime_repositories(uow)
            outbox = SQLAlchemyAgentOutboxEventWriter(uow)
            return await operation(repositories, outbox)

    async def assert_environment_enabled(
        self,
        *,
        target_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> None:
        async with self._uow_factory() as uow:
            await assert_runtime_environment_enabled(
                uow.session,
                target_type="agent",
                target_id=target_id,
                project_id=project_id,
                environment=environment,
            )
