from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Mapping
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.infra.errors import NotFoundError, ValidationError
from shared.runtime_environment import RUNTIME_ENVIRONMENTS, normalize_runtime_environment

ProjectEnvironmentKind = Literal["value", "secret"]

_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class PreparedProjectEnvironmentValue:
    kind: ProjectEnvironmentKind
    stored_value: str


def normalize_project_environment_key(value: str) -> str:
    key = str(value or "").strip()
    if not key or not _KEY_PATTERN.fullmatch(key):
        raise ValidationError(
            "Project Environment key must match ^[A-Za-z_][A-Za-z0-9_]*$"
        )
    return key


def normalize_project_environment_kind(value: str) -> ProjectEnvironmentKind:
    kind = str(value or "value").strip().lower()
    if kind not in {"value", "secret"}:
        raise ValidationError("Project Environment kind must be 'value' or 'secret'")
    return kind  # type: ignore[return-value]


async def read_project_environment_values(
    session: AsyncSession,
    *,
    project_id: UUID,
    environment: str,
    keys: set[str] | list[str] | tuple[str, ...],
) -> dict[str, PreparedProjectEnvironmentValue]:
    """Read only Project Environment keys referenced by the accepted Tool set.

    Secret values remain encrypted through Acceptance. The runtime keeps this
    prepared material process-local and decrypts only the subset referenced by the
    Tool being invoked, immediately before the HTTP/MCP adapter boundary.
    """

    normalized_environment = normalize_runtime_environment(environment)
    normalized_keys = sorted(
        {normalize_project_environment_key(key) for key in keys if str(key).strip()}
    )
    if not normalized_keys:
        return {}

    statement = text(
        """
        SELECT k.key, k.kind, v.stored_value
        FROM core.project_environment_keys AS k
        JOIN core.project_environment_values AS v
          ON v.key_id = k.id
         AND v.environment = :environment
        WHERE k.project_id = :project_id
          AND k.key IN :keys
          AND v.stored_value IS NOT NULL
          AND NOT v.revoked AND v.material_state = 'present'
        """
    ).bindparams(bindparam("keys", expanding=True))
    result = await session.execute(
        statement,
        {
            "project_id": project_id,
            "environment": normalized_environment,
            "keys": normalized_keys,
        },
    )
    values: dict[str, PreparedProjectEnvironmentValue] = {}
    for row in result.mappings():
        key = str(row["key"])
        values[key] = PreparedProjectEnvironmentValue(
            kind=normalize_project_environment_kind(str(row["kind"])),
            stored_value=str(row["stored_value"]),
        )
    return values


def materialize_project_environment_values(
    prepared: Mapping[str, PreparedProjectEnvironmentValue],
    *,
    encryption_key: str,
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, item in prepared.items():
        resolved[key] = (
            decrypt_secret(item.stored_value, encryption_key)
            if item.kind == "secret"
            else item.stored_value
        )
    return resolved


class ProjectEnvironmentService:
    """Project-scoped configuration with one logical key and per-environment values."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        encryption_key: str,
    ) -> None:
        self._session_factory = session_factory
        self._encryption_key = encryption_key

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

        async with self._session_factory() as session:
            result = await session.execute(
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
            names = ", ".join(missing)
            raise ValidationError(
                f"Project Environment key(s) do not exist in this Project: {names}"
            )

    async def list_keys(self, *, project_id: UUID) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            exists = await session.scalar(
                text("SELECT 1 FROM core.projects WHERE id = :project_id"),
                {"project_id": project_id},
            )
            if exists is None:
                raise NotFoundError("Project not found")

            result = await session.execute(
                text(
                    """
                    SELECT
                        k.id,
                        k.key,
                        k.kind,
                        k.created_at,
                        k.updated_at,
                        v.environment,
                        CASE WHEN k.kind = 'value' THEN v.stored_value ELSE NULL END AS stored_value,
                        (v.stored_value IS NOT NULL AND NOT v.revoked AND v.material_state = 'present') AS configured
                    FROM core.project_environment_keys AS k
                    LEFT JOIN core.project_environment_values AS v
                      ON v.key_id = k.id
                    WHERE k.project_id = :project_id
                    ORDER BY k.key, v.environment
                    """
                ),
                {"project_id": project_id},
            )

            by_id: dict[UUID, dict[str, object]] = {}
            for row in result.mappings():
                key_id = UUID(str(row["id"]))
                item = by_id.setdefault(
                    key_id,
                    {
                        "id": str(key_id),
                        "project_id": str(project_id),
                        "key": str(row["key"]),
                        "kind": str(row["kind"]),
                        "values": {
                            environment: {"configured": False, "value": None}
                            for environment in RUNTIME_ENVIRONMENTS
                        },
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    },
                )
                environment = row["environment"]
                if environment is None:
                    continue
                env = normalize_runtime_environment(str(environment))
                kind = normalize_project_environment_kind(str(row["kind"]))
                item_values = item["values"]
                assert isinstance(item_values, dict)
                item_values[env] = {
                    "configured": bool(row["configured"]),
                    "value": (
                        str(row["stored_value"])
                        if kind == "value" and row["configured"]
                        else None
                    ),
                }
            return list(by_id.values())

    async def resolve_values(
        self,
        *,
        project_id: UUID,
        environment: str,
        keys: set[str],
    ) -> dict[str, str]:
        async with self._session_factory() as session:
            prepared = await read_project_environment_values(
                session,
                project_id=project_id,
                environment=environment,
                keys=keys,
            )
        return materialize_project_environment_values(
            prepared,
            encryption_key=self._encryption_key,
        )

__all__ = [
    "PreparedProjectEnvironmentValue",
    "ProjectEnvironmentKind",
    "ProjectEnvironmentService",
    "materialize_project_environment_values",
    "normalize_project_environment_key",
    "normalize_project_environment_kind",
    "read_project_environment_values",
]
