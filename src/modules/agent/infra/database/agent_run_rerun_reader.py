from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from modules.agent.domain.run import AgentRun
from modules.agent.infra.database.agent_run_repository import SQLAlchemyAgentRunRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork

UnitOfWorkFactory = Callable[[], AgentUnitOfWork]


class SQLAlchemyAgentRunRerunReader:
    """Read one Agent Run through the Agent-owned short read UoW."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        async with self._uow_factory() as uow:
            return await SQLAlchemyAgentRunRepository(uow).get_by_id(run_id)
