from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import ConflictError, NotFoundError, ValidationError

RuntimeTargetType = Literal["agent", "network"]
RuntimeEnvironment = Literal["draft", "staging", "production"]
RUNTIME_ENVIRONMENTS: tuple[RuntimeEnvironment, ...] = (
    "draft",
    "staging",
    "production",
)


class RuntimeEnvironmentService:
    """Transaction boundary for runtime-environment management capabilities."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_states(
        self,
        *,
        target_type: RuntimeTargetType,
        target_id: UUID,
        project_id: UUID,
    ) -> dict[RuntimeEnvironment, RuntimeEnvironmentState]:
        async with self._session_factory() as session, session.begin():
            return await list_runtime_environment_states(
                session,
                target_type=target_type,
                target_id=target_id,
                project_id=project_id,
            )

    async def set_enabled(
        self,
        *,
        target_type: RuntimeTargetType,
        target_id: UUID,
        project_id: UUID,
        environment: str,
        enabled: bool,
        updated_by: UUID | None,
    ) -> RuntimeEnvironmentState:
        async with self._session_factory() as session, session.begin():
            return await set_runtime_environment_enabled(
                session,
                target_type=target_type,
                target_id=target_id,
                project_id=project_id,
                environment=environment,
                enabled=enabled,
                updated_by=updated_by,
            )


def build_runtime_environment_service() -> RuntimeEnvironmentService:
    from shared.composition_resources import SESSION_FACTORY

    return RuntimeEnvironmentService(SESSION_FACTORY)


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentState:
    target_type: RuntimeTargetType
    target_id: UUID
    project_id: UUID
    environment: RuntimeEnvironment
    enabled: bool
    updated_by: UUID | None
    updated_at: object | None

    def to_dict(self) -> dict[str, object]:
        return {
            "target_type": self.target_type,
            "target_id": str(self.target_id),
            "project_id": str(self.project_id),
            "environment": self.environment,
            "enabled": self.enabled,
            "updated_by": str(self.updated_by) if self.updated_by else None,
            "updated_at": self.updated_at,
        }


class RuntimeEnvironmentDisabledError(ConflictError):
    code = "RUNTIME_ENVIRONMENT_DISABLED"

    def __init__(
        self,
        *,
        target_type: RuntimeTargetType,
        target_id: UUID,
        environment: RuntimeEnvironment,
    ) -> None:
        self.target_type = target_type
        self.target_id = target_id
        self.environment = environment
        super().__init__(
            f"{self.code}: {target_type.capitalize()} runtime is disabled for {environment}"
        )


_TARGETS: dict[RuntimeTargetType, dict[str, str]] = {
    "agent": {
        "state_table": "agent.agent_runtime_environment_states",
        "target_table": "agent.agents",
        "target_column": "agent_id",
        "default_enabled": "CASE WHEN target.status = 'inactive' THEN false ELSE true END",
    },
    "network": {
        "state_table": "network.network_runtime_environment_states",
        "target_table": "network.networks",
        "target_column": "network_id",
        "default_enabled": "true",
    },
}


def normalize_runtime_environment(value: str | None) -> RuntimeEnvironment:
    normalized = (value or "draft").strip().lower()
    aliases = {
        "playground": "draft",
        "release": "production",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in RUNTIME_ENVIRONMENTS:
        raise ValidationError(f"Unsupported runtime environment: {value}")
    return normalized  # type: ignore[return-value]


def _target_config(target_type: RuntimeTargetType) -> dict[str, str]:
    try:
        return _TARGETS[target_type]
    except KeyError as exc:
        raise ValidationError(f"Unsupported runtime target type: {target_type}") from exc


async def ensure_runtime_environment_states(
    session: AsyncSession,
    *,
    target_type: RuntimeTargetType,
    target_id: UUID,
    project_id: UUID,
) -> None:
    config = _target_config(target_type)
    statement = text(
        f"""
        INSERT INTO {config['state_table']}
            (id, project_id, {config['target_column']}, environment, enabled, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            target.project_id,
            target.id,
            environment.name,
            {config['default_enabled']},
            now(),
            now()
        FROM {config['target_table']} AS target
        CROSS JOIN (VALUES ('draft'), ('staging'), ('production')) AS environment(name)
        WHERE target.id = :target_id
          AND target.project_id = :project_id
        ON CONFLICT ({config['target_column']}, environment) DO NOTHING
        """
    )
    result = await session.execute(
        statement,
        {"target_id": target_id, "project_id": project_id},
    )
    if result.rowcount == 0:
        exists = await session.scalar(
            text(
                f"SELECT 1 FROM {config['target_table']} "
                "WHERE id = :target_id AND project_id = :project_id"
            ),
            {"target_id": target_id, "project_id": project_id},
        )
        if exists is None:
            raise NotFoundError(f"{target_type.capitalize()} not found")


async def list_runtime_environment_states(
    session: AsyncSession,
    *,
    target_type: RuntimeTargetType,
    target_id: UUID,
    project_id: UUID,
) -> dict[RuntimeEnvironment, RuntimeEnvironmentState]:
    await ensure_runtime_environment_states(
        session,
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
    )
    config = _target_config(target_type)
    result = await session.execute(
        text(
            f"""
            SELECT
                project_id,
                {config['target_column']} AS target_id,
                environment,
                enabled,
                updated_by,
                updated_at
            FROM {config['state_table']}
            WHERE {config['target_column']} = :target_id
              AND project_id = :project_id
            ORDER BY CASE environment
                WHEN 'draft' THEN 1
                WHEN 'staging' THEN 2
                WHEN 'production' THEN 3
                ELSE 4
            END
            """
        ),
        {"target_id": target_id, "project_id": project_id},
    )
    states: dict[RuntimeEnvironment, RuntimeEnvironmentState] = {}
    for row in result.mappings():
        environment = normalize_runtime_environment(str(row["environment"]))
        states[environment] = RuntimeEnvironmentState(
            target_type=target_type,
            target_id=row["target_id"],
            project_id=row["project_id"],
            environment=environment,
            enabled=bool(row["enabled"]),
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
        )
    return states


async def set_runtime_environment_enabled(
    session: AsyncSession,
    *,
    target_type: RuntimeTargetType,
    target_id: UUID,
    project_id: UUID,
    environment: str,
    enabled: bool,
    updated_by: UUID | None,
) -> RuntimeEnvironmentState:
    normalized_environment = normalize_runtime_environment(environment)
    await ensure_runtime_environment_states(
        session,
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
    )
    config = _target_config(target_type)
    result = await session.execute(
        text(
            f"""
            UPDATE {config['state_table']}
            SET enabled = :enabled,
                updated_by = :updated_by,
                updated_at = now()
            WHERE {config['target_column']} = :target_id
              AND project_id = :project_id
              AND environment = :environment
            RETURNING
                project_id,
                {config['target_column']} AS target_id,
                environment,
                enabled,
                updated_by,
                updated_at
            """
        ),
        {
            "target_id": target_id,
            "project_id": project_id,
            "environment": normalized_environment,
            "enabled": enabled,
            "updated_by": updated_by,
        },
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise NotFoundError(f"{target_type.capitalize()} runtime environment not found")
    return RuntimeEnvironmentState(
        target_type=target_type,
        target_id=row["target_id"],
        project_id=row["project_id"],
        environment=normalized_environment,
        enabled=bool(row["enabled"]),
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    )


async def assert_runtime_environment_enabled(
    session: AsyncSession,
    *,
    target_type: RuntimeTargetType,
    target_id: UUID,
    project_id: UUID,
    environment: str,
) -> RuntimeEnvironmentState:
    normalized_environment = normalize_runtime_environment(environment)
    states = await list_runtime_environment_states(
        session,
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
    )
    state = states.get(normalized_environment)
    if state is None:
        raise NotFoundError(f"{target_type.capitalize()} runtime environment not found")
    if not state.enabled:
        raise RuntimeEnvironmentDisabledError(
            target_type=target_type,
            target_id=target_id,
            environment=normalized_environment,
        )
    return state


def runtime_states_payload(
    states: dict[RuntimeEnvironment, RuntimeEnvironmentState],
) -> dict[str, dict[str, object]]:
    return {
        environment: {
            "enabled": state.enabled,
            "updated_by": str(state.updated_by) if state.updated_by else None,
            "updated_at": state.updated_at,
        }
        for environment, state in states.items()
    }
