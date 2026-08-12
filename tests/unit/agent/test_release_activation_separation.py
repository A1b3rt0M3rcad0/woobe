import asyncio

from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus


class InMemoryReleaseRepository:
    def __init__(self, releases):
        self.items = {item.id: item for item in releases}

    async def get_by_id(self, release_id):
        return self.items.get(release_id)

    async def list_by_status(self, agent_id, status):
        expected = status.value if hasattr(status, "value") else status
        return [
            item
            for item in self.items.values()
            if item.agent_id == agent_id
            and (item.status.value if hasattr(item.status, "value") else item.status) == expected
        ]

    async def list_by_agent(self, agent_id):
        return [item for item in self.items.values() if item.agent_id == agent_id]

    async def save(self, release):
        self.items[release.id] = release
        return release


def test_activating_available_release_does_not_create_another_release():
    async def scenario():
        current = AgentRelease(version="v1.0.0", status=ReleaseStatus.production)
        current.snapshot_kind = "release"
        candidate = AgentRelease(
            project_id=current.project_id,
            agent_id=current.agent_id,
            version="v1.1.0",
            status=ReleaseStatus.released,
        )
        candidate.snapshot_kind = "release"
        repository = InMemoryReleaseRepository([current, candidate])
        lifecycle = ReleaseLifecycleUseCase(repository)

        output = await lifecycle.execute(
            candidate.agent_id,
            candidate.id,
            target_status="production",
        )

        assert output.id == candidate.id
        assert len(repository.items) == 2
        assert candidate.status == ReleaseStatus.production
        assert current.status == ReleaseStatus.released
        assert candidate.version == "v1.1.0"
        assert current.version == "v1.0.0"

    asyncio.run(scenario())
