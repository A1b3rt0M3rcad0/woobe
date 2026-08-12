from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from modules.agent.application.use_cases.network_snapshot_lifecycle import (
    NetworkAgentSnapshotLifecycle,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)


class FakeReleaseRepository:
    def __init__(self, releases: list[AgentRelease]) -> None:
        self.releases = {release.id: release for release in releases}

    async def save(self, release: AgentRelease) -> AgentRelease:
        self.releases[release.id] = release
        return release

    async def get_by_id(self, release_id: UUID) -> AgentRelease | None:
        return self.releases.get(release_id)

    async def get_by_version(self, agent_id: UUID, version: str) -> AgentRelease | None:
        return next(
            (
                release
                for release in self.releases.values()
                if release.agent_id == agent_id and release.version == version
            ),
            None,
        )

    async def get_active_production(self, agent_id: UUID) -> AgentRelease | None:
        matches = await self.list_by_status(agent_id, ReleaseStatus.production)
        return matches[0] if matches else None

    async def list_by_agent(self, agent_id: UUID) -> list[AgentRelease]:
        return [
            release
            for release in self.releases.values()
            if release.agent_id == agent_id
        ]

    async def paginate_by_agent(self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None):
        raise NotImplementedError

    async def list_by_status(
        self,
        agent_id: UUID,
        status: ReleaseStatus,
    ) -> list[AgentRelease]:
        return [
            release
            for release in self.releases.values()
            if release.agent_id == agent_id and release.status == status
        ]

    async def get_last_promoted(self, agent_id: UUID, *, exclude_id: UUID) -> AgentRelease | None:
        return None

    async def delete(self, release_id: UUID) -> None:
        self.releases.pop(release_id, None)


def make_release(
    *,
    project_id: UUID,
    agent_id: UUID,
    version: str,
    status: ReleaseStatus,
    snapshot_kind: str,
    schema: dict,
) -> AgentRelease:
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        name="Extractor",
        system_prompt="Extract the requested data",
        response_format={
            "enabled": True,
            "type": "json",
            "strict": True,
            "schema": schema,
        },
        output_schema=schema,
        provider="openai",
        model="gpt-4.1-mini",
        runtime_config={"tools": {"tool_ids": []}},
    )
    release.snapshot_kind = snapshot_kind
    return release


def test_snapshot_hash_is_stable_for_reordered_json_and_collections() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    left = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        status=ReleaseStatus.draft,
        snapshot_kind="draft",
        schema={"type": "object", "properties": {"name": {"type": "string"}}},
    )
    right = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="staging-r1",
        status=ReleaseStatus.staging,
        snapshot_kind="staging",
        schema={"properties": {"name": {"type": "string"}}, "type": "object"},
    )
    left.collection_ids = [UUID(int=2), UUID(int=1)]
    right.collection_ids = [UUID(int=1), UUID(int=2)]

    assert release_snapshots_equal(left, right)
    assert release_snapshot_hash(left) == release_snapshot_hash(right)


def test_output_contract_change_changes_snapshot_hash() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    staging = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="staging-r1",
        status=ReleaseStatus.staging,
        snapshot_kind="staging",
        schema={"message": "string"},
    )
    draft = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        status=ReleaseStatus.draft,
        snapshot_kind="draft",
        schema={"message": "string", "confidence": "number"},
    )

    assert not release_snapshots_equal(staging, draft)


@pytest.mark.asyncio
async def test_changed_draft_creates_new_staging_snapshot() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    staging = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="staging-r1",
        status=ReleaseStatus.staging,
        snapshot_kind="staging",
        schema={"message": "string"},
    )
    draft = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        status=ReleaseStatus.draft,
        snapshot_kind="draft",
        schema={"message": "string", "confidence": "number"},
    )
    repository = FakeReleaseRepository([draft, staging])

    result = await NetworkAgentSnapshotLifecycle(repository).promote_draft_to_staging(
        draft,
        user_id=None,
    )

    assert result.created is True
    assert result.release.version == "staging-r2"
    assert result.release.status == ReleaseStatus.staging
    assert result.release.output_schema == draft.output_schema
    assert staging.status == ReleaseStatus.archived


@pytest.mark.asyncio
async def test_equivalent_draft_reuses_current_staging() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    draft = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        status=ReleaseStatus.draft,
        snapshot_kind="draft",
        schema={"message": "string"},
    )
    staging = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="staging-r1",
        status=ReleaseStatus.staging,
        snapshot_kind="staging",
        schema={"message": "string"},
    )
    repository = FakeReleaseRepository([draft, staging])

    result = await NetworkAgentSnapshotLifecycle(repository).promote_draft_to_staging(
        draft,
        user_id=None,
    )

    assert result.created is False
    assert result.release.id == staging.id
    assert len(repository.releases) == 2


@pytest.mark.asyncio
async def test_network_publish_creates_available_release_without_agent_activation() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    staging = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="staging-r1",
        status=ReleaseStatus.staging,
        snapshot_kind="staging",
        schema={"message": "string"},
    )
    repository = FakeReleaseRepository([staging])
    lifecycle = NetworkAgentSnapshotLifecycle(repository)

    created = await lifecycle.publish_staging_for_network(staging, user_id=None)
    reused = await lifecycle.publish_staging_for_network(staging, user_id=None)

    assert created.created is True
    assert created.release.snapshot_kind == "release"
    assert created.release.status == ReleaseStatus.released
    assert reused.created is False
    assert reused.release.id == created.release.id
    assert not any(
        release.status == ReleaseStatus.production
        for release in repository.releases.values()
    )
