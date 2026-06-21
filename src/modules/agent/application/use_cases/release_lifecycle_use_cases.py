from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput
from modules.agent.application.use_cases.ai_use_cases import _release_to_output
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.domain.repositories import AgentReleaseRepository


_SINGLETON_STATUSES = {
    ReleaseStatus.draft,
    ReleaseStatus.staging,
    ReleaseStatus.production,
}


class AutoCreateReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, input_dto: CreateReleaseInput, change_kind: str = "change"):
        version = await self._next_version(input_dto.agent_id, change_kind)
        await self._archive_current(input_dto.agent_id, ReleaseStatus.draft)
        release = AgentRelease(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=version,
            status=ReleaseStatus.draft,
            prompt_version_id=input_dto.prompt_version_id,
            contract_version_id=input_dto.contract_version_id,
            knowledge_version_id=input_dto.knowledge_version_id,
            model_config_version_id=input_dto.model_config_version_id,
            name=input_dto.name,
            description=input_dto.description,
            system_prompt=input_dto.system_prompt,
            response_format=input_dto.response_format,
            output_schema=input_dto.output_schema,
            provider=input_dto.provider,
            model=input_dto.model,
            provider_credential_id=input_dto.provider_credential_id,
            fallback_provider=input_dto.fallback_provider,
            fallback_model=input_dto.fallback_model,
            fallback_credential_id=input_dto.fallback_credential_id,
            base_url=input_dto.base_url,
            temperature=input_dto.temperature,
            max_output_tokens=input_dto.max_output_tokens,
            session_mode=input_dto.session_mode,
            agent_status=input_dto.agent_status,
            collection_ids=input_dto.collection_ids,
            runtime_config=input_dto.runtime_config,
            release_notes=input_dto.release_notes,
            risk_score=input_dto.risk_score,
            created_by=input_dto.created_by,
        )
        saved = await self._release_repo.save(release)
        return _release_to_output(saved)

    async def _next_version(self, agent_id: UUID, change_kind: str) -> str:
        releases = await self._release_repo.list_by_agent(agent_id)
        return calculate_next_release_version([item.version for item in releases], change_kind)

    async def _archive_current(self, agent_id: UUID, status: ReleaseStatus) -> None:
        for release in await self._release_repo.list_by_status(agent_id, status):
            release.status = ReleaseStatus.archived
            await self._release_repo.save(release)


class ReleaseLifecycleUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(
        self,
        agent_id: UUID,
        release_id: UUID,
        input_dto=None,
        *,
        target_status: str = "production",
        user_id: UUID | None = None,
        copy_snapshot: bool = False,
        change_kind: str = "change",
    ):
        if input_dto is not None and user_id is None:
            user_id = getattr(input_dto, "user_id", None)
        release = await self._release_repo.get_by_id(release_id)
        if not release or release.agent_id != agent_id:
            raise ReleaseNotFoundError
        target = ReleaseStatus(target_status)
        if target not in _SINGLETON_STATUSES:
            raise ValueError("invalid release lifecycle target")
        if copy_snapshot:
            saved = await self._copy_to_status(release, target, user_id=user_id, change_kind=change_kind)
        else:
            saved = await self._move_to_status(release, target, user_id=user_id)
        return _release_to_output(saved)

    async def _move_to_status(self, release: AgentRelease, target: ReleaseStatus, *, user_id: UUID | None) -> AgentRelease:
        await self._archive_current(release.agent_id, target, exclude_id=release.id)
        release.status = target
        if target in (ReleaseStatus.staging, ReleaseStatus.production):
            release.promoted_by = user_id
            release.promoted_at = datetime.now(timezone.utc)
        return await self._release_repo.save(release)

    async def _copy_to_status(self, release: AgentRelease, target: ReleaseStatus, *, user_id: UUID | None, change_kind: str) -> AgentRelease:
        await self._archive_current(release.agent_id, target)
        version = await self._next_version(release.agent_id, change_kind)
        cloned = replace(
            release,
            id=AgentRelease().id,
            version=version,
            status=target,
            promoted_by=user_id if target in (ReleaseStatus.staging, ReleaseStatus.production) else None,
            promoted_at=datetime.now(timezone.utc) if target in (ReleaseStatus.staging, ReleaseStatus.production) else None,
            created_at=None,
            updated_at=None,
        )
        return await self._release_repo.save(cloned)

    async def _archive_current(self, agent_id: UUID, status: ReleaseStatus, *, exclude_id: UUID | None = None) -> None:
        for release in await self._release_repo.list_by_status(agent_id, status):
            if exclude_id is not None and release.id == exclude_id:
                continue
            release.status = ReleaseStatus.archived
            await self._release_repo.save(release)

    async def _next_version(self, agent_id: UUID, change_kind: str) -> str:
        releases = await self._release_repo.list_by_agent(agent_id)
        return calculate_next_release_version([item.version for item in releases], change_kind)
