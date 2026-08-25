from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.runtime_repositories import (
    AgentRuntimeRepositories,
    build_agent_runtime_repositories,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork

ResultT = TypeVar("ResultT")
UnitOfWorkFactory = Callable[[], AgentUnitOfWork]
RuntimeTransactionOperation = Callable[
    [AgentRuntimeRepositories, OutboxEventWriter],
    Awaitable[ResultT],
]


class AgentRuntimeTransactionRunner:
    """Transitional persistence boundary used only by Acceptance/Finalization/read scopes."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        read_uow_factory: UnitOfWorkFactory | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._read_uow_factory = read_uow_factory or uow_factory

    async def run(self, operation: RuntimeTransactionOperation[ResultT]) -> ResultT:
        async with self._uow_factory() as uow:
            repositories = build_agent_runtime_repositories(uow)
            outbox = SQLAlchemyAgentOutboxEventWriter(uow)
            return await operation(repositories, outbox)

    async def read(self, operation: RuntimeTransactionOperation[ResultT]) -> ResultT:
        """Execute a short SQL read scope that ends in rollback, never COMMIT."""

        async with self._read_uow_factory() as uow:
            repositories = build_agent_runtime_repositories(uow)
            outbox = SQLAlchemyAgentOutboxEventWriter(uow)
            return await operation(repositories, outbox)
