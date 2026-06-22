from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_compatibility import classify_release_change


_VERSIONED_PRODUCTION_SOURCES = {ReleaseStatus.draft, ReleaseStatus.staging}
_EXECUTION_FIELDS = (
    "prompt_version_id",
    "contract_version_id",
    "knowledge_version_id",
    "model_config_version_id",
    "name",
    "description",
    "system_prompt",
    "response_format",
    "output_schema",
    "provider",
    "model",
    "base_url",
    "temperature",
    "max_output_tokens",
    "session_mode",
    "agent_status",
    "collection_ids",
    "runtime_config",
    "risk_score",
)


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

    async def _copy_to_production_release(self, release: AgentRelease, *, user_id, change_kind=None, **metadata) -> AgentRelease:
        note_text = metadata.get("release_notes")
        current = await self._get_singleton(release.agent_id, ReleaseStatus.production)
        if current is not None and _execution_snapshot_equal(current, release):
            if note_text is not None and current.release_notes != note_text:
                current.release_notes = note_text
                return await self._release_repo.save(current)
            return current
        detected_kind = classify_release_change(current, release)
        await self._archive_current(release.agent_id, ReleaseStatus.production)
        version = await self._next_version(release.agent_id, detected_kind)
        clone = replace(
            release,
            id=AgentRelease().id,
            version=version,
            status=ReleaseStatus.production,
            release_notes=note_text,
            promoted_by=user_id,
            promoted_at=datetime.now(timezone.utc),
            created_at=None,
            updated_at=None,
        )
        return await self._release_repo.save(clone)


def _execution_snapshot_equal(left: AgentRelease, right: AgentRelease) -> bool:
    return all(getattr(left, field_name) == getattr(right, field_name) for field_name in _EXECUTION_FIELDS)
