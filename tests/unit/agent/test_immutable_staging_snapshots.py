import asyncio
from copy import deepcopy

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


def test_promoting_draft_creates_new_immutable_staging_snapshots():
    async def scenario():
        draft = AgentRelease(
            version="draft",
            status=ReleaseStatus.draft,
            system_prompt="first prompt",
            session_mode="stateful",
            agent_status="active",
        )
        draft.snapshot_kind = "draft"
        repository = InMemoryReleaseRepository([draft])
        lifecycle = ReleaseLifecycleUseCase(repository)

        first_output = await lifecycle.execute(
            draft.agent_id,
            draft.id,
            target_status="staging",
        )
        first = deepcopy(await repository.get_by_id(first_output.id))

        draft.system_prompt = "second prompt"
        second_output = await lifecycle.execute(
            draft.agent_id,
            draft.id,
            target_status="staging",
        )
        second = await repository.get_by_id(second_output.id)
        archived_first = await repository.get_by_id(first.id)

        assert first.id != second.id
        assert first.version == "staging-r1"
        assert second.version == "staging-r2"
        assert first.snapshot_kind == "staging"
        assert second.snapshot_kind == "staging"
        assert first.system_prompt == "first prompt"
        assert second.system_prompt == "second prompt"
        assert archived_first.status == ReleaseStatus.archived
        assert archived_first.system_prompt == "first prompt"
        assert second.session_mode == "stateful"
        assert second.agent_status == "active"

    asyncio.run(scenario())


def test_publishing_historical_staging_creates_release_without_mutating_source():
    async def scenario():
        staging = AgentRelease(
            version="staging-r3",
            status=ReleaseStatus.archived,
            system_prompt="validated prompt",
        )
        staging.snapshot_kind = "staging"
        repository = InMemoryReleaseRepository([staging])
        lifecycle = ReleaseLifecycleUseCase(repository)

        output = await lifecycle.execute(
            staging.agent_id,
            staging.id,
            target_status="production",
        )
        published = await repository.get_by_id(output.id)
        source = await repository.get_by_id(staging.id)

        assert published.id != source.id
        assert published.status == ReleaseStatus.production
        assert published.snapshot_kind == "release"
        assert published.system_prompt == "validated prompt"
        assert source.status == ReleaseStatus.archived
        assert source.snapshot_kind == "staging"
        assert source.version == "staging-r3"

    asyncio.run(scenario())
