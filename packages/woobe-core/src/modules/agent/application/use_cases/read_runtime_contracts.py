from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from modules.agent.application.interfaces.repositories import AgentReleaseRepository
from modules.agent.domain.release_compatibility import effective_output_schema
from shared.contracts.errors import NotFoundError, ValidationError
from shared.contracts.runtime_contracts import (
    RuntimeContractSnapshot,
    external_context_contract_schema,
)


@dataclass(frozen=True, slots=True)
class ReadRuntimeContractsInput:
    agent_id: UUID
    project_id: UUID
    environment: str


class ReadRuntimeContractsUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(
        self,
        input_dto: ReadRuntimeContractsInput,
    ) -> RuntimeContractSnapshot:
        if input_dto.environment not in {"staging", "production"}:
            raise ValidationError("Runtime Key binding is incomplete")

        releases = await self._release_repo.list_by_agent(input_dto.agent_id)
        release = next(
            (
                candidate
                for candidate in releases
                if candidate.project_id == input_dto.project_id
                and str(getattr(candidate.status, "value", candidate.status))
                == input_dto.environment
            ),
            None,
        )
        if release is None:
            raise NotFoundError(
                f"Agent {input_dto.environment} Release not found"
            )

        return RuntimeContractSnapshot(
            release_id=str(release.id),
            release_version=str(release.version),
            output_contract=effective_output_schema(release),
            external_context=external_context_contract_schema(
                release.external_context_contract
            ),
        )


__all__ = [
    "ReadRuntimeContractsInput",
    "ReadRuntimeContractsUseCase",
]
