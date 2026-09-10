from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from modules.agent.application.use_cases.release_lifecycle_use_cases import (
    ReleaseLifecycleUseCase,
    _release_to_output,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_compatibility import classify_release_change
from shared.contracts.errors import ConflictError


_EXECUTION_FIELDS = (
    "prompt_version_id",
    "contract_version_id",
    "knowledge_version_id",
    "model_config_version_id",
    "provider_model_id",
    "fallback_provider_model_id",
    "name",
    "description",
    "behavior_spec",
    "system_prompt",
    "response_format",
    "output_schema",
    "provider",
    "model",
    "provider_credential_id",
    "fallback_provider",
    "fallback_model",
    "fallback_credential_id",
    "base_url",
    "temperature",
    "max_output_tokens",
    "session_mode",
    "agent_status",
    "collection_ids",
    "runtime_config",
    "risk_score",
)


def _release_time(release: AgentRelease) -> float:
    value = release.created_at or release.promoted_at
    return value.timestamp() if value is not None else 0.0


class AutoCompatibleReleaseLifecycleUseCase(ReleaseLifecycleUseCase):
    async def execute(
        self,
        agent_id,
        release_id,
        input_dto=None,
        *,
        target_status: str = "production",
        user_id=None,
        copy_snapshot: bool = False,
        change_kind: str = "change",
    ):
        if input_dto is not None and user_id is None:
            user_id = getattr(input_dto, "user_id", None)

        release = await self._release_repo.get_by_id(release_id)
        target_value = getattr(target_status, "value", target_status)

        if target_value == ReleaseStatus.released.value:
            if release is None or release.agent_id != agent_id:
                from modules.agent.domain.errors import ReleaseNotFoundError
                raise ReleaseNotFoundError
            if (
                release.status != ReleaseStatus.staging
                or getattr(release, "snapshot_kind", None) != "staging"
            ):
                raise ConflictError("An immutable Agent Release can only be created from current Staging")
            saved = await self._copy_to_available_release(
                release,
                user_id=user_id,
                input_dto=input_dto,
            )
            return _release_to_output(saved)

        if target_value == ReleaseStatus.production.value and release is not None:
            if release.status == ReleaseStatus.draft:
                raise ConflictError("Draft must be promoted to Staging before Production")
            if getattr(release, "snapshot_kind", None) == "staging":
                existing = await self._find_equivalent_release(release)
                if existing is not None:
                    release_id = existing.id
                    copy_snapshot = False
                else:
                    copy_snapshot = True

        return await super().execute(
            agent_id,
            release_id,
            input_dto,
            target_status=target_value,
            user_id=user_id,
            copy_snapshot=copy_snapshot,
            change_kind=change_kind,
        )

    async def _copy_to_available_release(
        self,
        release: AgentRelease,
        *,
        user_id,
        input_dto=None,
    ) -> AgentRelease:
        existing = await self._find_equivalent_release(release)
        if existing is not None:
            return existing

        current = await self._get_singleton(release.agent_id, ReleaseStatus.production)
        detected_kind = classify_release_change(current, release)
        version = await self._next_version(release.agent_id, detected_kind)
        release_notes = getattr(input_dto, "release_notes", None) if input_dto is not None else None
        clone = _clone_release_snapshot(
            release,
            version=version,
            status=ReleaseStatus.released,
            release_notes=release_notes,
            promoted_by=None,
        )
        clone.created_by = user_id or release.created_by
        clone.promoted_by = None
        clone.promoted_at = None
        return await self._release_repo.save(clone)

    async def _find_equivalent_release(self, source: AgentRelease) -> AgentRelease | None:
        releases = await self._release_repo.list_by_agent(source.agent_id)
        equivalent = [
            item
            for item in releases
            if getattr(item, "snapshot_kind", None) == "release"
            and _execution_snapshot_equal(item, source)
        ]
        return max(equivalent, key=_release_time) if equivalent else None

    async def _copy_to_production_release(
        self,
        release: AgentRelease,
        *,
        user_id,
        change_kind=None,
        **metadata,
    ) -> AgentRelease:
        note_text = metadata.get("release_notes")
        current = await self._get_singleton(release.agent_id, ReleaseStatus.production)
        if current is not None and _execution_snapshot_equal(current, release):
            return current
        detected_kind = classify_release_change(current, release)
        await self._archive_current(release.agent_id, ReleaseStatus.production)
        version = await self._next_version(release.agent_id, detected_kind)
        clone = _clone_release_snapshot(
            release,
            version=version,
            status=ReleaseStatus.production,
            release_notes=note_text,
            promoted_by=user_id,
        )
        return await self._release_repo.save(clone)


def _clone_release_snapshot(
    source: AgentRelease,
    *,
    version: str,
    status: ReleaseStatus,
    release_notes: str | None,
    promoted_by,
) -> AgentRelease:
    clone = AgentRelease()
    clone.project_id = source.project_id
    clone.agent_id = source.agent_id
    for field_name in _EXECUTION_FIELDS:
        setattr(clone, field_name, deepcopy(getattr(source, field_name)))
    clone.version = version
    clone.status = status
    clone.snapshot_kind = "release"
    clone.release_notes = release_notes
    clone.created_by = source.created_by
    clone.promoted_by = promoted_by
    clone.promoted_at = datetime.now(timezone.utc) if status == ReleaseStatus.production else None
    clone.created_at = None
    clone.updated_at = None
    return clone


def _execution_snapshot_equal(left: AgentRelease, right: AgentRelease) -> bool:
    return all(getattr(left, field_name) == getattr(right, field_name) for field_name in _EXECUTION_FIELDS)
