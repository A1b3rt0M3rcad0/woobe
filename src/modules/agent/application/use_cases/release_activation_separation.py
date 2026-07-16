from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError
from shared.infra.errors import ConflictError


async def _activate_existing_release(self, release, *, user_id: UUID | None):
    if getattr(release, "snapshot_kind", None) != "release":
        raise ConflictError("Only an immutable Agent Release can be activated in Production")
    if release.status == ReleaseStatus.production:
        return release
    await self._archive_current(
        release.agent_id,
        ReleaseStatus.production,
        exclude_id=release.id,
    )
    release.status = ReleaseStatus.production
    release.promoted_by = user_id
    release.promoted_at = datetime.now(timezone.utc)
    return await self._release_repo.save(release)


async def _archive_current(self, agent_id, status, *, exclude_id=None):
    for release in await self._release_repo.list_by_status(agent_id, status):
        if exclude_id is not None and release.id == exclude_id:
            continue
        release.status = (
            ReleaseStatus.released
            if status == ReleaseStatus.production
            else ReleaseStatus.archived
        )
        await self._release_repo.save(release)


async def _get_singleton(self, agent_id, status):
    items = await self._release_repo.list_by_status(agent_id, status)
    if not items:
        return None
    primary = sorted(
        items,
        key=lambda item: item.updated_at or item.created_at or datetime.min,
        reverse=True,
    )[0]
    for stale in items:
        if stale.id == primary.id:
            continue
        stale.status = (
            ReleaseStatus.released
            if status == ReleaseStatus.production
            else ReleaseStatus.archived
        )
        await self._release_repo.save(stale)
    return primary


async def _execute_with_separate_activation(
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
    release = await self._release_repo.get_by_id(release_id)
    if not release or release.agent_id != agent_id:
        raise ReleaseNotFoundError
    if input_dto is not None and user_id is None:
        user_id = getattr(input_dto, "user_id", None)

    if target_status == ReleaseStatus.production.value:
        snapshot_kind = getattr(release, "snapshot_kind", None)
        if snapshot_kind == "draft" or release.status == ReleaseStatus.draft:
            raise ConflictError("Draft must be promoted to Staging before Production")
        if snapshot_kind == "release":
            saved = await _activate_existing_release(self, release, user_id=user_id)
            from modules.agent.application.use_cases.release_lifecycle_use_cases import _release_to_output
            return _release_to_output(saved)

    return await self._separate_activation_base_execute(
        agent_id,
        release_id,
        input_dto,
        target_status=target_status,
        user_id=user_id,
        copy_snapshot=copy_snapshot,
        change_kind=change_kind,
    )


def install_release_activation_separation() -> None:
    from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase

    if hasattr(ReleaseLifecycleUseCase, "_separate_activation_base_execute"):
        return
    ReleaseLifecycleUseCase._separate_activation_base_execute = ReleaseLifecycleUseCase.execute  # type: ignore[attr-defined]
    ReleaseLifecycleUseCase.execute = _execute_with_separate_activation  # type: ignore[assignment]
    ReleaseLifecycleUseCase._archive_current = _archive_current  # type: ignore[assignment]
    ReleaseLifecycleUseCase._get_singleton = _get_singleton  # type: ignore[assignment]
    ReleaseLifecycleUseCase._activate_existing_release = _activate_existing_release  # type: ignore[attr-defined]
