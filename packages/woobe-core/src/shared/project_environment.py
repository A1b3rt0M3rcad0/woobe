from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Mapping
from uuid import UUID

from sqlalchemy import text
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
    """Read only the keys required by one Tool execution.

    Secret values remain encrypted here. Materialization happens after the runtime
    Acceptance transaction so decrypted values never enter durable snapshots.
    """

    normalized_environment = normalize_runtime_environment(environment)
    normalized_keys = sorted(
        {normalize_project_environment_key(key) for key in keys if str(key).strip()}
    )
    if not normalized_keys:
        return {}

    result = await session.execute(
        text(
            """
            SELECT k.key, k.kind, v.stored_value
            FROM core.project_environment_keys AS k
            JOIN core.project_environment_values AS v
              ON v.key_id = k.id
             AND v.environment = :environment
            WHERE k.project_id = :project_id
              AND k.key = ANY(:keys)
            """
        ),
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
                        v.stored_value
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
                    "configured": True,
                    "value": (
                        str(row["stored_value"])
                        if kind == "value"
                        else None
                    ),
                }
            return list(by_id.values())

    async def upsert_key(
        self,
        *,
        project_id: UUID,
        key: str,
        kind: str,
        values: Mapping[str, str | None],
        clear_environments: list[str] | tuple[str, ...] = (),
    ) -> dict[str, object]:
        normalized_key = normalize_project_environment_key(key)
        normalized_kind = normalize_project_environment_kind(kind)

        normalized_values: dict[str, str] = {}
        for raw_environment, raw_value in values.items():
            environment = normalize_runtime_environment(raw_environment)
            if raw_value is None:
                continue
            normalized_values[environment] = str(raw_value)

        clear = {
            normalize_runtime_environment(environment)
            for environment in clear_environments
        }

        async with self._session_factory() as session, session.begin():
            project_exists = await session.scalar(
                text("SELECT 1 FROM core.projects WHERE id = :project_id"),
                {"project_id": project_id},
            )
            if project_exists is None:
                raise NotFoundError("Project not found")

            existing = (
                await session.execute(
                    text(
                        """
                        SELECT id, kind
                        FROM core.project_environment_keys
                        WHERE project_id = :project_id
                          AND key = :key
                        FOR UPDATE
                        """
                    ),
                    {"project_id": project_id, "key": normalized_key},
                )
            ).mappings().one_or_none()

            kind_changed = (
                existing is not None
                and normalize_project_environment_kind(str(existing["kind"]))
                != normalized_kind
            )

            if existing is None:
                key_id = await session.scalar(
                    text(
                        """
                        INSERT INTO core.project_environment_keys
                            (id, project_id, key, kind, created_at, updated_at)
                        VALUES
                            (gen_random_uuid(), :project_id, :key, :kind, now(), now())
                        RETURNING id
                        """
                    ),
                    {
                        "project_id": project_id,
                        "key": normalized_key,
                        "kind": normalized_kind,
                    },
                )
            else:
                key_id = existing["id"]
                await session.execute(
                    text(
                        """
                        UPDATE core.project_environment_keys
                        SET kind = :kind,
                            updated_at = now()
                        WHERE id = :key_id
                        """
                    ),
                    {"key_id": key_id, "kind": normalized_kind},
                )
                if kind_changed:
                    # Values cannot safely survive a value <-> secret semantic change.
                    await session.execute(
                        text(
                            "DELETE FROM core.project_environment_values WHERE key_id = :key_id"
                        ),
                        {"key_id": key_id},
                    )

            for environment in clear:
                await session.execute(
                    text(
                        """
                        DELETE FROM core.project_environment_values
                        WHERE key_id = :key_id
                          AND environment = :environment
                        """
                    ),
                    {"key_id": key_id, "environment": environment},
                )

            for environment, raw_value in normalized_values.items():
                stored_value = (
                    encrypt_secret(raw_value, self._encryption_key)
                    if normalized_kind == "secret"
                    else raw_value
                )
                await session.execute(
                    text(
                        """
                        INSERT INTO core.project_environment_values
                            (id, key_id, environment, stored_value, created_at, updated_at)
                        VALUES
                            (gen_random_uuid(), :key_id, :environment, :stored_value, now(), now())
                        ON CONFLICT (key_id, environment)
                        DO UPDATE SET
                            stored_value = EXCLUDED.stored_value,
                            updated_at = now()
                        """
                    ),
                    {
                        "key_id": key_id,
                        "environment": environment,
                        "stored_value": stored_value,
                    },
                )

        items = await self.list_keys(project_id=project_id)
        for item in items:
            if item["key"] == normalized_key:
                return item
        raise NotFoundError("Project Environment key not found after update")

    async def delete_key(self, *, project_id: UUID, key: str) -> None:
        normalized_key = normalize_project_environment_key(key)
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                text(
                    """
                    DELETE FROM core.project_environment_keys
                    WHERE project_id = :project_id
                      AND key = :key
                    RETURNING id
                    """
                ),
                {"project_id": project_id, "key": normalized_key},
            )
            if result.scalar_one_or_none() is None:
                raise NotFoundError("Project Environment key not found")


def build_project_environment_service() -> ProjectEnvironmentService:
    from shared.composition_resources import SESSION_FACTORY

    return ProjectEnvironmentService(
        SESSION_FACTORY,
        encryption_key=Settings().encryption_key,
    )


__all__ = [
    "PreparedProjectEnvironmentValue",
    "ProjectEnvironmentKind",
    "ProjectEnvironmentService",
    "build_project_environment_service",
    "materialize_project_environment_values",
    "normalize_project_environment_key",
    "normalize_project_environment_kind",
    "read_project_environment_values",
]
