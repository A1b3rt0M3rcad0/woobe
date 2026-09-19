from __future__ import annotations

from uuid import UUID

from sqlalchemy import bindparam, text

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.errors import ValidationError
from shared.project_environment import (
    PreparedProjectEnvironmentValue,
    materialize_project_environment_values,
    normalize_project_environment_key,
    read_project_environment_values,
)


class SQLAlchemyProjectEnvironmentReader:
    """Read Project Environment material inside the Agent Acceptance transaction."""

    def __init__(
        self,
        uow: AgentUnitOfWork,
        *,
        encryption_key: str | None = None,
    ) -> None:
        self._uow = uow
        self._encryption_key = encryption_key

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

    async def require_keys(
        self,
        *,
        project_id: UUID,
        keys: set[str],
    ) -> None:
        normalized = {
            normalize_project_environment_key(key)
            for key in keys
            if str(key).strip()
        }
        if not normalized:
            return

        result = await self._uow.session.execute(
            text(
                """
                SELECT key
                FROM core.project_environment_keys
                WHERE project_id = :project_id
                  AND key IN :keys
                """
            ).bindparams(bindparam("keys", expanding=True)),
            {
                "project_id": project_id,
                "keys": sorted(normalized),
            },
        )
        existing = {str(row[0]) for row in result.all()}
        missing = sorted(normalized - existing)
        if missing:
            raise ValidationError(
                "Project Environment key(s) do not exist in this Project: "
                + ", ".join(missing)
            )

    async def resolve_values(
        self,
        *,
        project_id: UUID,
        environment: str,
        keys: set[str],
    ) -> dict[str, str]:
        if self._encryption_key is None:
            raise RuntimeError("Project Environment encryption key is unavailable")
        prepared = await self.read_values(
            project_id=project_id,
            environment=environment,
            keys=keys,
        )
        return materialize_project_environment_values(
            prepared,
            encryption_key=self._encryption_key,
        )
