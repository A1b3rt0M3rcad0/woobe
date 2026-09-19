from __future__ import annotations

from uuid import UUID

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.project_environment import (
    PreparedProjectEnvironmentValue,
    read_project_environment_values,
)


class SQLAlchemyProjectEnvironmentReader:
    """Read Project Environment material inside the Agent Acceptance transaction."""

    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def read_values(
        self,
        *,
        project_id: UUID,
        environment: str,
        keys: set[str],
    ) -> dict[str, PreparedProjectEnvironmentValue]:
        return await read_project_environment_values(
            self._uow.session,
            project_id=project_id,
            environment=environment,
            keys=keys,
        )
