from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.provider_model_repository import (
    ProviderModelRepository,
)
from modules.agent.application.interfaces.repositories import (
    AgentReleaseRepository,
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.agent.domain.enums import (
    AgentStatus,
    CredentialStatus,
    ProviderModelStatus,
    ReleaseStatus,
)
from shared.contracts.errors import ConflictError, ValidationError
from shared.security.crypto import encrypt_secret


_BLOCKING_RELEASE_STATUSES = {
    ReleaseStatus.draft.value,
    ReleaseStatus.staging.value,
    ReleaseStatus.production.value,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _id(value: Any) -> str | None:
    return str(value) if value else None


def _item(
    *,
    type: str,
    id: Any,
    name: str | None = None,
    field: str | None = None,
    status: Any = None,
    agent_id: Any = None,
    agent_name: str | None = None,
    version: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "type": type,
        "id": _id(id),
        "name": name,
        "field": field,
        "status": _status_value(status),
        "agent_id": _id(agent_id),
        "agent_name": agent_name,
        "version": version,
        "reason": reason,
    }


def _usage(
    blocking: list[dict[str, Any]],
    informational: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "can_delete": len(blocking) == 0,
        "blocking": blocking,
        "informational": informational or [],
    }


def _is_archived(value: Any) -> bool:
    return _status_value(value) == "archived"


class ProviderCredentialUsageUseCase:
    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        provider_model_repo: ProviderModelRepository,
        agent_repo: AgentRepository,
        release_repo: AgentReleaseRepository,
    ) -> None:
        self._credential_repo = credential_repo
        self._provider_model_repo = provider_model_repo
        self._agent_repo = agent_repo
        self._release_repo = release_repo

    async def execute(self, credential_id: UUID) -> dict[str, Any]:
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        blocking: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None, str | None]] = set()

        def add(item: dict[str, Any]) -> None:
            key = (str(item.get("type")), item.get("id"), item.get("field"))
            if key not in seen:
                seen.add(key)
                blocking.append(item)

        provider_models = await self._provider_model_repo.list_by_credential(credential_id)
        active_model_ids = {
            item.id for item in provider_models if not _is_archived(item.status)
        }
        for model in provider_models:
            if not _is_archived(model.status):
                add(
                    _item(
                        type="provider_model",
                        id=model.id,
                        name=model.name,
                        status=model.status,
                        field="provider_credential_id",
                    )
                )

        agents = await self._agent_repo.list_by_project(credential.project_id)
        active_agents = [
            agent
            for agent in agents
            if _status_value(getattr(agent, "status", None))
            != AgentStatus.archived.value
        ]
        for agent in active_agents:
            if getattr(agent, "provider_credential_id", None) == credential_id:
                add(
                    _item(
                        type="agent",
                        id=agent.id,
                        name=agent.name,
                        status=agent.status,
                        field="provider_credential_id",
                    )
                )
            if getattr(agent, "fallback_credential_id", None) == credential_id:
                add(
                    _item(
                        type="agent",
                        id=agent.id,
                        name=agent.name,
                        status=agent.status,
                        field="fallback_credential_id",
                    )
                )
            if getattr(agent, "provider_model_id", None) in active_model_ids:
                add(
                    _item(
                        type="agent",
                        id=agent.id,
                        name=agent.name,
                        status=agent.status,
                        field="provider_model_id",
                    )
                )
            if getattr(agent, "fallback_provider_model_id", None) in active_model_ids:
                add(
                    _item(
                        type="agent",
                        id=agent.id,
                        name=agent.name,
                        status=agent.status,
                        field="fallback_provider_model_id",
                    )
                )

            releases = await self._release_repo.list_by_agent(agent.id)
            for release in releases:
                status = _status_value(release.status)
                if status not in _BLOCKING_RELEASE_STATUSES:
                    continue
                if getattr(release, "provider_credential_id", None) == credential_id:
                    add(
                        _item(
                            type="release",
                            id=release.id,
                            name=release.name,
                            status=release.status,
                            field="provider_credential_id",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            version=release.version,
                        )
                    )
                if getattr(release, "fallback_credential_id", None) == credential_id:
                    add(
                        _item(
                            type="release",
                            id=release.id,
                            name=release.name,
                            status=release.status,
                            field="fallback_credential_id",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            version=release.version,
                        )
                    )
                if getattr(release, "provider_model_id", None) in active_model_ids:
                    add(
                        _item(
                            type="release",
                            id=release.id,
                            name=release.name,
                            status=release.status,
                            field="provider_model_id",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            version=release.version,
                        )
                    )
                if getattr(release, "fallback_provider_model_id", None) in active_model_ids:
                    add(
                        _item(
                            type="release",
                            id=release.id,
                            name=release.name,
                            status=release.status,
                            field="fallback_provider_model_id",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            version=release.version,
                        )
                    )

        return _usage(blocking)


class ProviderModelUsageUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        agent_repo: AgentRepository,
        release_repo: AgentReleaseRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._agent_repo = agent_repo
        self._release_repo = release_repo

    async def execute(self, provider_model_id: UUID) -> dict[str, Any]:
        provider_model = await self._provider_model_repo.get_by_id(provider_model_id)
        if provider_model is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError

            raise ModelConfigNotFoundError
        blocking: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None, str | None]] = set()

        def add(item: dict[str, Any]) -> None:
            key = (str(item.get("type")), item.get("id"), item.get("field"))
            if key not in seen:
                seen.add(key)
                blocking.append(item)

        agents = await self._agent_repo.list_by_project(provider_model.project_id)
        active_agents = [
            agent
            for agent in agents
            if _status_value(getattr(agent, "status", None))
            != AgentStatus.archived.value
        ]
        for agent in active_agents:
            if getattr(agent, "provider_model_id", None) == provider_model_id:
                add(
                    _item(
                        type="agent",
                        id=agent.id,
                        name=agent.name,
                        status=agent.status,
                        field="provider_model_id",
                    )
                )
            if getattr(agent, "fallback_provider_model_id", None) == provider_model_id:
                add(
                    _item(
                        type="agent",
                        id=agent.id,
                        name=agent.name,
                        status=agent.status,
                        field="fallback_provider_model_id",
                    )
                )

            releases = await self._release_repo.list_by_agent(agent.id)
            for release in releases:
                status = _status_value(release.status)
                if status not in _BLOCKING_RELEASE_STATUSES:
                    continue
                if getattr(release, "provider_model_id", None) == provider_model_id:
                    add(
                        _item(
                            type="release",
                            id=release.id,
                            name=release.name,
                            status=release.status,
                            field="provider_model_id",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            version=release.version,
                        )
                    )
                if getattr(release, "fallback_provider_model_id", None) == provider_model_id:
                    add(
                        _item(
                            type="release",
                            id=release.id,
                            name=release.name,
                            status=release.status,
                            field="fallback_provider_model_id",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            version=release.version,
                        )
                    )

        return _usage(blocking)


class RotateProviderCredentialUseCase:
    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        encryption_key: str,
    ) -> None:
        self._credential_repo = credential_repo
        self._encryption_key = encryption_key

    async def execute(self, credential_id: UUID, data: dict[str, Any]) -> Any:
        secret = str(data.get("secret") or "").strip()
        if not secret:
            raise ValidationError("New API key is required")
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        if _is_archived(credential.status):
            raise ValidationError("Archived credential cannot be rotated")
        metadata = dict(credential.metadata or {})
        metadata["previous_rotated_at"] = metadata.get("rotated_at")
        metadata["rotated_at"] = _now_iso()
        metadata["rotation_count"] = int(metadata.get("rotation_count") or 0) + 1
        if data.get("expires_at") is not None:
            metadata["expires_at"] = data.get("expires_at") or None
        credential.encrypted_secret = encrypt_secret(secret, self._encryption_key)
        credential.status = CredentialStatus.active
        credential.metadata = metadata
        return await self._credential_repo.update(credential)


class RevokeProviderCredentialUseCase:
    def __init__(self, credential_repo: ProviderCredentialRepository) -> None:
        self._credential_repo = credential_repo

    async def execute(
        self,
        credential_id: UUID,
        data: dict[str, Any] | None = None,
    ) -> Any:
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        metadata = dict(credential.metadata or {})
        metadata["revoked_at"] = _now_iso()
        reason = (data or {}).get("reason")
        if reason:
            metadata["revoked_reason"] = str(reason)
        credential.status = CredentialStatus.revoked
        credential.metadata = metadata
        return await self._credential_repo.update(credential)


class ArchiveProviderCredentialUseCase:
    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        usage_use_case: ProviderCredentialUsageUseCase,
    ) -> None:
        self._credential_repo = credential_repo
        self._usage_use_case = usage_use_case

    async def execute(self, credential_id: UUID) -> Any:
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        usage = await self._usage_use_case.execute(credential_id)
        if not usage["can_delete"]:
            raise ConflictError("Credential is still in use")
        metadata = dict(credential.metadata or {})
        metadata["deleted_at"] = _now_iso()
        metadata["delete_mode"] = "soft_delete"
        credential.status = CredentialStatus.archived
        credential.metadata = metadata
        return await self._credential_repo.update(credential)


class ArchiveProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        usage_use_case: ProviderModelUsageUseCase,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._usage_use_case = usage_use_case

    async def execute(self, provider_model_id: UUID) -> Any:
        provider_model = await self._provider_model_repo.get_by_id(provider_model_id)
        if provider_model is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError

            raise ModelConfigNotFoundError
        usage = await self._usage_use_case.execute(provider_model_id)
        if not usage["can_delete"]:
            raise ConflictError("Provider model is still in use")
        metadata = dict(provider_model.metadata or {})
        metadata["deleted_at"] = _now_iso()
        metadata["delete_mode"] = "soft_delete"
        provider_model.status = ProviderModelStatus.archived
        provider_model.metadata = metadata
        return await self._provider_model_repo.update(provider_model)
