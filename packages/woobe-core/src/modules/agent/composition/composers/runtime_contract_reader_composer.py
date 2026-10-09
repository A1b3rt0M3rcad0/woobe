from __future__ import annotations

from typing import Any

from modules.agent.application.use_cases.read_runtime_contracts import (
    ReadRuntimeContractsInput,
    ReadRuntimeContractsUseCase,
)
from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.infra.database.asac_runtime_release_repository import SQLAlchemySelectedAgentReleaseRepository
from shared.infra.transactional_handler import TransactionalHandler


def build_agent_runtime_contract_reader(
    *,
    uow: Any | None = None,
) -> TransactionalHandler:
    unit_of_work = uow or build_agent_read_uow()
    release_repo = SQLAlchemySelectedAgentReleaseRepository(unit_of_work)
    use_case = ReadRuntimeContractsUseCase(release_repo)
    return TransactionalHandler(unit_of_work, use_case.execute)


__all__ = [
    "ReadRuntimeContractsInput",
    "build_agent_runtime_contract_reader",
]
