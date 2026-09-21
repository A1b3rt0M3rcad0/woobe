from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.domain.release_compatibility import effective_output_schema
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from shared.infra.errors import NotFoundError, ValidationError
from shared.runtime_contract_compatibility import (
    RuntimeContractSnapshot,
    external_context_contract_schema,
)


class AgentRuntimeContractReader:
    def __init__(self, uow_factory: Callable[[], Any] = build_agent_read_uow) -> None:
        self._uow_factory = uow_factory

    async def read(
        self,
        *,
        agent_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> RuntimeContractSnapshot:
        if environment not in {"staging", "production"}:
            raise ValidationError("Runtime Key binding is incomplete")

        async with self._uow_factory() as uow:
            releases = await SQLAlchemyAgentReleaseRepository(uow).list_by_agent(agent_id)
            release = next(
                (
                    candidate
                    for candidate in releases
                    if candidate.project_id == project_id
                    and str(getattr(candidate.status, "value", candidate.status))
                    == environment
                ),
                None,
            )
            if release is None:
                raise NotFoundError(f"Agent {environment} Release not found")

            return RuntimeContractSnapshot(
                release_id=str(release.id),
                release_version=str(release.version),
                output_contract=effective_output_schema(release),
                external_context=external_context_contract_schema(
                    getattr(release, "external_context_contract", None)
                ),
            )


def build_agent_runtime_contract_reader() -> AgentRuntimeContractReader:
    return AgentRuntimeContractReader()


__all__ = [
    "AgentRuntimeContractReader",
    "build_agent_runtime_contract_reader",
]
