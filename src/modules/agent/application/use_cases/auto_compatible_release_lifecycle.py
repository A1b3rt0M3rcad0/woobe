from __future__ import annotations

from datetime import datetime, timezone

from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_compatibility import classify_release_change


_VERSIONED_PRODUCTION_SOURCES = {ReleaseStatus.draft, ReleaseStatus.staging}


class AutoCompatibleReleaseLifecycleUseCase(ReleaseLifecycleUseCase):
    async def execute(self, agent_id, release_id, input_dto=None, *, target_status: str = "production", user_id=None, copy_snapshot: bool = False, change_kind: str = "change"):
        release = await self._release_repo.get_by_id(release_id)
        if target_status == ReleaseStatus.production.value and release is not None:
            copy_snapshot = release.status in _VERSIONED_PRODUCTION_SOURCES
        return await super().execute(
            agent_id,
            release_id,
            input_dto,
            target_status=target_status,
            user_id=user_id,
            copy_snapshot=copy_snapshot,
            change_kind=change_kind,
        )

    async def _copy_to_production_release(self, release: AgentRelease, *, user_id, change_kind=None) -> AgentRelease:
        current = await self._get_singleton(release.agent_id, ReleaseStatus.production)
        if current is not None and current.output_schema == release.output_schema and current.response_format == release.response_format and current.system_prompt == release.system_prompt and current.model == release.model and current.provider == release.provider:
            return current
        detected_kind = classify_release_change(current, release)
        await self._archive_current(release.agent_id, ReleaseStatus.production)
        version = await self._next_version(release.agent_id, detected_kind)
        clone = AgentRelease(
            project_id=release.project_id,
            agent_id=release.agent_id,
            version=version,
            status=ReleaseStatus.production,
            prompt_version_id=release.prompt_version_id,
            contract_version_id=release.contract_version_id,
            knowledge_version_id=release.knowledge_version_id,
            model_config_version_id=release.model_config_version_id,
            name=release.name,
            description=release.description,
            system_prompt=release.system_prompt,
            response_format=release.response_format,
            output_schema=release.output_schema,
            provider=release.provider,
            model=release.model,
            provider_credential_id=release.provider_credential_id,
            fallback_provider=release.fallback_provider,
            fallback_model=release.fallback_model,
            fallback_credential_id=release.fallback_credential_id,
            base_url=release.base_url,
            temperature=release.temperature,
            max_output_tokens=release.max_output_tokens,
            session_mode=release.session_mode,
            agent_status=release.agent_status,
            collection_ids=release.collection_ids,
            runtime_config=release.runtime_config,
            release_notes=release.release_notes,
            risk_score=release.risk_score,
            created_by=release.created_by,
            promoted_by=user_id,
            promoted_at=datetime.now(timezone.utc),
        )
        return await self._release_repo.save(clone)
