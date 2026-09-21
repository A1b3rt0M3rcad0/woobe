from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.use_cases.read_runtime_contracts import (
    ReadRuntimeContractsInput,
    ReadRuntimeContractsUseCase,
)
from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from shared.infra.transactional_handler import TransactionalHandler
from shared.runtime_contract_compatibility import RuntimeContractSnapshot


class AgentRuntimeContractReader:
    def __init__(
        self,
        handler: TransactionalHandler[
            ReadRuntimeContractsInput,
            RuntimeContractSnapshot,
        ],
    ) -> None:
        self._handler = handler

    async def read(
        self,
        *,
        agent_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> RuntimeContractSnapshot:
        return await self._handler(
            ReadRuntimeContractsInput(
                agent_id=agent_id,
                project_id=project_id,
                environment=environment,
            )
        )


def build_agent_runtime_contract_reader(
    *,
    uow: Any | None = None,
) -> AgentRuntimeContractReader:
    unit_of_work = uow or build_agent_read_uow()
    release_repo = SQLAlchemyAgentReleaseRepository(unit_of_work)
    use_case = ReadRuntimeContractsUseCase(release_repo)
    handler = TransactionalHandler(unit_of_work, use_case.execute)
    return AgentRuntimeContractReader(handler)


__all__ = [
    "AgentRuntimeContractReader",
    "build_agent_runtime_contract_reader",
]
