from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    AutoCompatibleReleaseLifecycleUseCase,
)
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import (
    KnowledgeSafeReleaseLifecycleUseCase,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from shared.infra.errors import ValidationError


class FakeReleaseRepository:
    def __init__(self, releases: list[AgentRelease]) -> None:
        self.releases = {release.id: release for release in releases}

    async def save(self, release: AgentRelease) -> AgentRelease:
        self.releases[release.id] = release
        return release

    async def get_by_id(self, release_id: UUID) -> AgentRelease | None:
        return self.releases.get(release_id)

    async def get_by_version(self, agent_id: UUID, version: str) -> AgentRelease | None:
        return next((item for item in self.releases.values() if item.agent_id == agent_id and item.version == version), None)

    async def get_active_production(self, agent_id: UUID) -> AgentRelease | None:
        return next((item for item in self.releases.values() if item.agent_id == agent_id and item.status == ReleaseStatus.production), None)

    async def list_by_agent(self, agent_id: UUID) -> list[AgentRelease]:
        return [item for item in self.releases.values() if item.agent_id == agent_id]

    async def list_by_status(self, agent_id: UUID, status: ReleaseStatus) -> list[AgentRelease]:
        return [item for item in self.releases.values() if item.agent_id == agent_id and item.status == status]

    async def get_last_promoted(self, agent_id: UUID, *, exclude_id: UUID) -> AgentRelease | None:
        return None


class FakeValidator:
    async def validate(self, release: AgentRelease) -> None:
        return None


class FakeActivationRepository:
    def __init__(self) -> None:
        self.items = []

    async def save(self, activation):
        self.items.append(activation)
        return activation


def make_snapshot(*, project_id, agent_id, version, status, kind, prompt='prompt') -> AgentRelease:
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        system_prompt=prompt,
        provider='openai',
        model='gpt-4o-mini',
        session_mode='stateful',
    )
    release.snapshot_kind = kind
    return release


@pytest.mark.asyncio
async def test_create_release_from_staging_does_not_deploy() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    staging = make_snapshot(
        project_id=project_id,
        agent_id=agent_id,
        version='staging-r1',
        status=ReleaseStatus.staging,
        kind='staging',
    )
    repo = FakeReleaseRepository([staging])

    result = await AutoCompatibleReleaseLifecycleUseCase(repo).execute(
        agent_id,
        staging.id,
        target_status='released',
    )

    assert result.status == ReleaseStatus.released
    assert result.snapshot_kind == 'release'
    assert result.promoted_at is None
    assert await repo.get_active_production(agent_id) is None


@pytest.mark.asyncio
async def test_create_release_reuses_equivalent_immutable_snapshot() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    staging = make_snapshot(
        project_id=project_id,
        agent_id=agent_id,
        version='staging-r2',
        status=ReleaseStatus.staging,
        kind='staging',
    )
    existing = make_snapshot(
        project_id=project_id,
        agent_id=agent_id,
        version='v1.0.0',
        status=ReleaseStatus.released,
        kind='release',
    )
    repo = FakeReleaseRepository([staging, existing])

    result = await AutoCompatibleReleaseLifecycleUseCase(repo).execute(
        agent_id,
        staging.id,
        target_status='released',
    )

    assert result.id == existing.id
    assert len(await repo.list_by_agent(agent_id)) == 2


@pytest.mark.asyncio
async def test_deploying_existing_release_records_reactivation_event() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = make_snapshot(
        project_id=project_id,
        agent_id=agent_id,
        version='v1.0.0',
        status=ReleaseStatus.production,
        kind='release',
        prompt='old',
    )
    candidate = make_snapshot(
        project_id=project_id,
        agent_id=agent_id,
        version='v1.1.0',
        status=ReleaseStatus.released,
        kind='release',
        prompt='new',
    )
    repo = FakeReleaseRepository([production, candidate])
    activations = FakeActivationRepository()
    use_case = KnowledgeSafeReleaseLifecycleUseCase(repo, FakeValidator(), activations)

    result = await use_case.execute(
        agent_id,
        candidate.id,
        SimpleNamespace(user_id=None, change_description='Reactivate validated Release'),
        target_status='production',
    )

    assert result.id == candidate.id
    assert production.status == ReleaseStatus.released
    assert len(activations.items) == 1
    assert activations.items[0].action == 'reactivate'
    assert activations.items[0].change_description == 'Reactivate validated Release'
    assert activations.items[0].previous_release_id == production.id
    assert activations.items[0].release_id == candidate.id


@pytest.mark.asyncio
async def test_production_reactivation_requires_audit_reason() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = make_snapshot(project_id=project_id, agent_id=agent_id, version='v1', status=ReleaseStatus.production, kind='release')
    candidate = make_snapshot(project_id=project_id, agent_id=agent_id, version='v2', status=ReleaseStatus.released, kind='release')
    use_case = KnowledgeSafeReleaseLifecycleUseCase(FakeReleaseRepository([production, candidate]), FakeValidator(), FakeActivationRepository())

    with pytest.raises(ValidationError, match='activation reason'):
        await use_case.execute(agent_id, candidate.id, SimpleNamespace(user_id=None), target_status='production')
