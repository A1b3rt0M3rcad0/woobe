from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import uuid6

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_snapshot import release_snapshots_equal
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.application.interfaces.repositories import AgentReleaseRepository


@dataclass(frozen=True)
class NetworkSnapshotResolution:
    release: AgentRelease
    created: bool


class NetworkAgentSnapshotLifecycle:
    """Creates immutable Agent snapshots required by a Network promotion.

    Network Releases never activate standalone Agent Production. A Release
    created here is stored as ``released`` and remains available for explicit
    activation in the Agent Playground.
    """

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def promote_draft_to_staging(
        self,
        draft: AgentRelease,
        *,
        user_id: UUID | None,
    ) -> NetworkSnapshotResolution:
        staging_items = await self._release_repo.list_by_status(
            draft.agent_id,
            ReleaseStatus.staging,
        )
        current = self._latest(staging_items)
        if current is not None and release_snapshots_equal(current, draft):
            return NetworkSnapshotResolution(current, created=False)

        for staging in staging_items:
            staging.status = ReleaseStatus.archived
            await self._release_repo.save(staging)

        releases = await self._release_repo.list_by_agent(draft.agent_id)
        staged = self._clone(
            draft,
            version=self._next_staging_version(releases),
            status=ReleaseStatus.staging,
            snapshot_kind="staging",
            user_id=user_id,
        )
        return NetworkSnapshotResolution(
            await self._release_repo.save(staged),
            created=True,
        )

    async def publish_staging_for_network(
        self,
        staging: AgentRelease,
        *,
        user_id: UUID | None,
    ) -> NetworkSnapshotResolution:
        releases = await self._release_repo.list_by_agent(staging.agent_id)
        immutable = [
            item
            for item in releases
            if getattr(item, "snapshot_kind", None) == "release"
        ]
        equivalent = next(
            (
                item
                for item in sorted(immutable, key=self._sort_key, reverse=True)
                if release_snapshots_equal(item, staging)
            ),
            None,
        )
        if equivalent is not None:
            return NetworkSnapshotResolution(equivalent, created=False)

        previous = self._latest(immutable)
        change_kind = classify_release_change(previous, staging)
        version = calculate_next_release_version(
            [item.version for item in immutable],
            change_kind,
        )
        released = self._clone(
            staging,
            version=version,
            status=ReleaseStatus.released,
            snapshot_kind="release",
            user_id=user_id,
        )
        return NetworkSnapshotResolution(
            await self._release_repo.save(released),
            created=True,
        )

    @staticmethod
    def _clone(
        source: AgentRelease,
        *,
        version: str,
        status: ReleaseStatus,
        snapshot_kind: str,
        user_id: UUID | None,
    ) -> AgentRelease:
        clone = deepcopy(source)
        clone.id = uuid6.uuid7()
        clone.version = version
        clone.status = status
        clone.snapshot_kind = snapshot_kind
        clone.promoted_by = user_id
        clone.promoted_at = datetime.now(timezone.utc)
        clone.created_at = None
        clone.updated_at = None
        return clone

    @staticmethod
    def _latest(items: list[AgentRelease]) -> AgentRelease | None:
        return max(items, key=NetworkAgentSnapshotLifecycle._sort_key) if items else None

    @staticmethod
    def _sort_key(release: AgentRelease) -> float:
        value = release.promoted_at or release.updated_at or release.created_at
        return value.timestamp() if value is not None else 0.0

    @staticmethod
    def _next_staging_version(releases: list[AgentRelease]) -> str:
        used = {item.version for item in releases}
        number = 1 + sum(
            1
            for item in releases
            if getattr(item, "snapshot_kind", None) == "staging"
        )
        while f"staging-r{number}" in used:
            number += 1
        return f"staging-r{number}"
