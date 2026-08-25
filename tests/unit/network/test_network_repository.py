from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.infra.database.repositories import NetworkRepository
from shared.infra.errors import ConflictError


class FakeResult:
    def __init__(self, *, values=None, scalar=None) -> None:
        self._values = list(values or [])
        self._scalar = scalar

    def scalars(self):
        return self._values

    def scalar_one_or_none(self):
        return self._scalar


class FakeSession:
    def __init__(self, network, available_agent_ids) -> None:
        self.network = network
        self.available_agent_ids = set(available_agent_ids)
        self.execute_calls = 0

    async def get(self, model, resource_id):
        return self.network

    async def execute(self, statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return FakeResult(values=self.available_agent_ids)
        return FakeResult(scalar=self.network)


class FakeListSession:
    def __init__(self, networks) -> None:
        self.networks = list(networks)

    async def execute(self, statement):
        return FakeResult(values=self.networks)


@pytest.mark.asyncio
async def test_legacy_project_lookup_returns_none_without_networks():
    repository = NetworkRepository(FakeListSession([]))

    assert await repository.get_by_project(uuid4()) is None


@pytest.mark.asyncio
async def test_legacy_project_lookup_returns_the_only_network():
    network = SimpleNamespace(id=uuid4())
    repository = NetworkRepository(FakeListSession([network]))

    assert await repository.get_by_project(uuid4()) is network


@pytest.mark.asyncio
async def test_legacy_project_lookup_rejects_ambiguous_networks():
    repository = NetworkRepository(
        FakeListSession(
            [
                SimpleNamespace(id=uuid4()),
                SimpleNamespace(id=uuid4()),
            ]
        )
    )

    with pytest.raises(ConflictError, match="select a Network explicitly"):
        await repository.get_by_project(uuid4())


@pytest.mark.asyncio
async def test_save_draft_rejects_agent_outside_network_project():
    project_id = uuid4()
    network = SimpleNamespace(project_id=project_id)
    foreign_agent_id = uuid4()
    session = FakeSession(network, available_agent_ids=[])
    repository = NetworkRepository(session)

    with pytest.raises(ConflictError, match="inactive or unavailable Agents"):
        await repository.save_draft(
            uuid4(),
            expected_revision=0,
            name="Project Network",
            description="",
            definition={"nodes": [{"agent_id": str(foreign_agent_id)}]},
        )

    assert session.execute_calls == 1


@pytest.mark.asyncio
async def test_save_draft_rejects_inactive_agent():
    project_id = uuid4()
    network = SimpleNamespace(project_id=project_id)
    inactive_agent_id = uuid4()
    session = FakeSession(network, available_agent_ids=[])
    repository = NetworkRepository(session)

    with pytest.raises(ConflictError, match=str(inactive_agent_id)):
        await repository.save_draft(
            uuid4(),
            expected_revision=0,
            name="Project Network",
            description="",
            definition={"nodes": [{"agent_id": str(inactive_agent_id)}]},
        )

    assert session.execute_calls == 1


@pytest.mark.asyncio
async def test_save_draft_rejects_duplicate_agent_binding():
    project_id = uuid4()
    agent_id = uuid4()
    network = SimpleNamespace(project_id=project_id)
    session = FakeSession(network, available_agent_ids=[agent_id])
    repository = NetworkRepository(session)

    with pytest.raises(ConflictError, match="cannot appear more than once"):
        await repository.save_draft(
            uuid4(),
            expected_revision=0,
            name="Project Network",
            description="",
            definition={
                "nodes": [
                    {"agent_id": str(agent_id)},
                    {"agent_id": str(agent_id)},
                ]
            },
        )

    assert session.execute_calls == 0


@pytest.mark.asyncio
async def test_save_draft_accepts_active_agents_owned_by_network_project():
    project_id = uuid4()
    agent_id = uuid4()
    network = SimpleNamespace(project_id=project_id)
    session = FakeSession(network, available_agent_ids=[agent_id])
    repository = NetworkRepository(session)

    saved = await repository.save_draft(
        uuid4(),
        expected_revision=0,
        name="Project Network",
        description="",
        definition={"nodes": [{"agent_id": str(agent_id)}]},
    )

    assert saved is network
    assert session.execute_calls == 2
