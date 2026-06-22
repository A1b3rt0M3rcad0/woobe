from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput, CreateReleaseOutput
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.domain.repositories import AgentReleaseRepository


_SINGLETON_STATUSES = {ReleaseStatus.draft, ReleaseStatus.staging, ReleaseStatus.production}
_SNAPSHOT_FIELDS = (
    "project_id", "agent_id", "prompt_version_id", "contract_version_id",
    "knowledge_version_id", "model_config_version_id", "name", "description",
    "system_prompt", "response_format", "output_schema", "provider", "model",
    "provider_credential_id", "fallback_provider", "fallback_model",
    "fallback_credential_id", "base_url", "temperature", "max_output_tokens",
    "session_mode", "agent_status", "collection_ids", "runtime_config",
    "risk_score", "created_by",
)


def _release_to_output(saved: AgentRelease) -> CreateReleaseOutput:
    return CreateReleaseOutput(
        id=saved.id, project_id=saved.project_id, agent_id=saved.agent_id,
        version=saved.version, status=saved.status,
        prompt_version_id=saved.prompt_version_id,
        contract_version_id=saved.contract_version_id,
        knowledge_version_id=saved.knowledge_version_id,
        model_config_version_id=saved.model_config_version_id,
        name=saved.name, description=saved.description,
        system_prompt=saved.system_prompt, response_format=saved.response_format,
        output_schema=saved.output_schema, provider=saved.provider,
        model=saved.model, provider_credential_id=saved.provider_credential_id,
        fallback_provider=saved.fallback_provider, fallback_model=saved.fallback_model,
        fallback_credential_id=saved.fallback_credential_id, base_url=saved.base_url,
        temperature=saved.temperature, max_output_tokens=saved.max_output_tokens,
        session_mode=saved.session_mode, agent_status=saved.agent_status,
        collection_ids=saved.collection_ids, runtime_config=saved.runtime_config,
        release_notes=saved.release_notes, risk_score=saved.risk_score,
        created_by=saved.created_by, promoted_by=saved.promoted_by,
        promoted_at=saved.promoted_at, created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


class AutoCreateReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, input_dto: CreateReleaseInput, change_kind: str = "change"):
        draft = await self._get_singleton(input_dto.agent_id, ReleaseStatus.draft)
        if draft is None:
            draft = AgentRelease(project_id=input_dto.project_id, agent_id=input_dto.agent_id, version="draft", status=ReleaseStatus.draft)
        self._copy_input_to_release(input_dto, draft)
        draft.version = "draft"
        draft.status = ReleaseStatus.draft
        return _release_to_output(await self._release_repo.save(draft))

    async def _get_singleton(self, agent_id: UUID, status: ReleaseStatus) -> AgentRelease | None:
        items = await self._release_repo.list_by_status(agent_id, status)
        if not items:
            return None
        primary = sorted(items, key=lambda item: item.updated_at or item.created_at or datetime.min, reverse=True)[0]
        for stale in items:
            if stale.id != primary.id:
                stale.status = ReleaseStatus.archived
                await self._release_repo.save(stale)
        return primary

    def _copy_input_to_release(self, input_dto: CreateReleaseInput, release: AgentRelease) -> None:
        for field_name in _SNAPSHOT_FIELDS:
            setattr(release, field_name, getattr(input_dto, field_name))
        release.release_notes = getattr(input_dto, "release_notes", None)


class ReleaseLifecycleUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, agent_id: UUID, release_id: UUID, input_dto=None, *, target_status: str = "production", user_id: UUID | None = None, copy_snapshot: bool = False, change_kind: str = "change"):
        release_notes = getattr(input_dto, "release_notes", None) if input_dto is not None else None
        if input_dto is not None and user_id is None:
            user_id = getattr(input_dto, "user_id", None)
        release = await self._release_repo.get_by_id(release_id)
        if not release or release.agent_id != agent_id:
            raise ReleaseNotFoundError
        target = ReleaseStatus(target_status)
        if target not in _SINGLETON_STATUSES:
            raise ValueError("invalid release lifecycle target")
        if target in (ReleaseStatus.draft, ReleaseStatus.staging):
            saved = await self._upsert_singleton_snapshot(release, target, user_id=user_id)
        elif copy_snapshot:
            saved = await self._copy_to_production_release(release, user_id=user_id, change_kind=change_kind, release_notes=release_notes)
        else:
            saved = await self._move_to_status(release, target, user_id=user_id)
        return _release_to_output(saved)

    async def _upsert_singleton_snapshot(self, source: AgentRelease, target: ReleaseStatus, *, user_id: UUID | None) -> AgentRelease:
        current = await self._get_singleton(source.agent_id, target)
        if current is None:
            current = AgentRelease(project_id=source.project_id, agent_id=source.agent_id, version=target.value, status=target)
        self._copy_snapshot(source, current)
        current.version = target.value
        current.status = target
        if target == ReleaseStatus.staging:
            current.promoted_by = user_id
            current.promoted_at = datetime.now(timezone.utc)
        return await self._release_repo.save(current)

    async def _move_to_status(self, release: AgentRelease, target: ReleaseStatus, *, user_id: UUID | None) -> AgentRelease:
        await self._archive_current(release.agent_id, target, exclude_id=release.id)
        release.status = target
        if target == ReleaseStatus.production:
            release.promoted_by = user_id
            release.promoted_at = datetime.now(timezone.utc)
        return await self._release_repo.save(release)

    async def _copy_to_production_release(self, release: AgentRelease, *, user_id: UUID | None, change_kind: str, release_notes: str | None = None) -> AgentRelease:
        await self._archive_current(release.agent_id, ReleaseStatus.production)
        version = await self._next_version(release.agent_id, change_kind)
        cloned = replace(release, id=AgentRelease().id, version=version, status=ReleaseStatus.production, release_notes=release_notes, promoted_by=user_id, promoted_at=datetime.now(timezone.utc), created_at=None, updated_at=None)
        return await self._release_repo.save(cloned)

    async def _archive_current(self, agent_id: UUID, status: ReleaseStatus, *, exclude_id: UUID | None = None) -> None:
        for release in await self._release_repo.list_by_status(agent_id, status):
            if exclude_id is not None and release.id == exclude_id:
                continue
            release.status = ReleaseStatus.archived
            await self._release_repo.save(release)

    async def _get_singleton(self, agent_id: UUID, status: ReleaseStatus) -> AgentRelease | None:
        items = await self._release_repo.list_by_status(agent_id, status)
        if not items:
            return None
        primary = sorted(items, key=lambda item: item.updated_at or item.created_at or datetime.min, reverse=True)[0]
        for stale in items:
            if stale.id != primary.id:
                stale.status = ReleaseStatus.archived
                await self._release_repo.save(stale)
        return primary

    async def _next_version(self, agent_id: UUID, change_kind: str) -> str:
        releases = await self._release_repo.list_by_agent(agent_id)
        historical_versions = [item.version for item in releases if item.status not in (ReleaseStatus.draft, ReleaseStatus.staging)]
        return calculate_next_release_version(historical_versions, change_kind)

    def _copy_snapshot(self, source: AgentRelease, target: AgentRelease) -> None:
        for field_name in _SNAPSHOT_FIELDS:
            setattr(target, field_name, getattr(source, field_name))
