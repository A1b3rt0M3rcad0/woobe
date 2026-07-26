from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import (
    KnowledgeSafeRollbackReleaseUseCase,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus


class FakeReleaseRepository:
    def __init__(self, releases):
        self.releases = {release.id: release for release in releases}

    async def get_by_id(self, release_id):
        return self.releases.get(release_id)

    async def get_active_production(self, agent_id):
        return next((release for release in self.releases.values() if release.agent_id == agent_id and release.status == ReleaseStatus.production), None)

    async def list_by_agent(self, agent_id):
        return [release for release in self.releases.values() if release.agent_id == agent_id]

    async def list_by_status(self, agent_id, status):
        return [release for release in self.releases.values() if release.agent_id == agent_id and release.status == status]

    async def save(self, release):
        self.releases[release.id] = release
        return release


class FakeValidator:
    async def validate(self, release):
        return None


class FakeActivationRepository:
    def __init__(self):
        self.items = []

    async def save(self, activation):
        self.items.append(activation)
        return activation


def _release(*, project_id, agent_id, version, status):
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        provider="openai",
        model="model-a",
        session_mode="stateful",
    )
    release.snapshot_kind = "release"
    return release


@pytest.mark.asyncio
async def test_rollback_records_audit_description_and_action() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = _release(project_id=project_id, agent_id=agent_id, version="v2", status=ReleaseStatus.production)
    target = _release(project_id=project_id, agent_id=agent_id, version="v1", status=ReleaseStatus.released)
    repo = FakeReleaseRepository([production, target])
    activations = FakeActivationRepository()
    use_case = KnowledgeSafeRollbackReleaseUseCase(
        repo,
        FakeValidator(),
        activations,
        activation_action="rollback",
    )

    result = await use_case.execute(
        agent_id,
        target.id,
        SimpleNamespace(user_id=None, change_description="Rollback after validation regression"),
    )

    assert result.id == target.id
    assert len(activations.items) == 1
    assert activations.items[0].action == "rollback"
    assert activations.items[0].change_description == "Rollback after validation regression"
    assert activations.items[0].previous_release_id == production.id
