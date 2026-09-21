from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.domain.release_compatibility import effective_output_schema
from modules.agent.infra.database.models import AgentReleaseModel
from shared.infra.database.session import create_session_factory
from shared.infra.errors import NotFoundError, ValidationError
from shared.runtime_contract_compatibility import (
    RuntimeContractSnapshot,
    external_context_contract_schema,
)


class AgentRuntimeContractReader:
    def __init__(self) -> None:
        self._session_factory = create_session_factory(DATABASE_ENGINE)

    async def read(
        self,
        *,
        agent_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> RuntimeContractSnapshot:
        if environment not in {"staging", "production"}:
            raise ValidationError("Runtime Key binding is incomplete")

        async with self._session_factory() as session:
            release = await session.scalar(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.agent_id == agent_id,
                    AgentReleaseModel.project_id == project_id,
                    AgentReleaseModel.status == environment,
                )
                .order_by(AgentReleaseModel.created_at.desc())
                .limit(1)
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
