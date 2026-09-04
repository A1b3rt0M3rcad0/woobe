import asyncio
from uuid import uuid4

from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.infra.services.release_environment_separation import (
    _copy_agent_snapshot_detached,
)


class ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class FakeSession:
    def __init__(self, production):
        self.production = production
        self.calls = 0
        self.added = []

    async def scalars(self, _query):
        self.calls += 1
        if self.calls == 1:
            return ScalarResult([])
        return ScalarResult([self.production])

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        return None


class Service:
    @staticmethod
    def _same_agent_snapshot(left, right):
        return left.system_prompt == right.system_prompt


def test_network_publish_creates_available_release_without_changing_agent_production():
    async def scenario():
        project_id = uuid4()
        agent_id = uuid4()
        production = AgentReleaseModel(
            project_id=project_id,
            agent_id=agent_id,
            version="v1.0.0",
            status="production",
            snapshot_kind="release",
            system_prompt="current standalone production",
        )
        staging = AgentReleaseModel(
            project_id=project_id,
            agent_id=agent_id,
            version="staging-r2",
            status="staging",
            snapshot_kind="staging",
            system_prompt="network validated change",
        )
        session = FakeSession(production)

        created = await _copy_agent_snapshot_detached(
            Service(),
            session,
            staging,
            target="release",
            promoted_by=None,
        )

        assert created is not production
        assert created is not staging
        assert created.status == "released"
        assert created.snapshot_kind == "release"
        assert created.system_prompt == "network validated change"
        assert production.status == "production"
        assert production.version == "v1.0.0"
        assert staging.status == "staging"
        assert session.added == [created]

    asyncio.run(scenario())

