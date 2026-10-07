from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database.provider_dependency_reader import (
    SQLProviderDependencyReader,
)
from modules.network.infra.database.dependency_impact_reader import (
    NetworkDependencyImpactReader,
)
from modules.chat_surface.infra.database.dependency_impact_reader import (
    SurfaceDependencyImpactReader,
)


class SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_frozen_network_and_surface_keep_indirect_model_impact_after_draft_changes():
    project, model, agent, release, network, surface = [uuid4() for _ in range(6)]
    native = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
        execute=AsyncMock(
            return_value=SimpleNamespace(
                all=lambda: [SimpleNamespace(id=release, agent_id=agent)]
            )
        ),
    )
    network_session = SimpleNamespace(
        scalars=AsyncMock(
            side_effect=[
                SimpleNamespace(
                    all=lambda: [
                        SimpleNamespace(
                            id=network,
                            name="Frozen Network",
                            draft_definition={"nodes": []},
                        )
                    ]
                ),
                SimpleNamespace(
                    all=lambda: [
                        SimpleNamespace(
                            network_id=network,
                            resolved_bindings={
                                "node": {
                                    "agent_id": str(agent),
                                    "release_id": str(release),
                                }
                            },
                        )
                    ]
                ),
            ]
        )
    )
    surface_session = SimpleNamespace(
        scalars=AsyncMock(
            return_value=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        id=surface,
                        name="Support",
                        status="active",
                        target_type="network",
                        target_id=network,
                        target_release_id=uuid4(),
                    )
                ]
            )
        )
    )
    reader = SQLProviderDependencyReader(
        SimpleNamespace(session=native),
        NetworkDependencyImpactReader(
            lambda: SessionContext(network_session)
        ).consumers,
        SurfaceDependencyImpactReader(
            lambda: SessionContext(surface_session)
        ).consumers,
    )
    impact = await reader.downstream_consumers(project, {model})
    assert [(item["type"], item["id"]) for item in impact] == [
        ("network", str(network)),
        ("surface", str(surface)),
    ]


@pytest.mark.asyncio
async def test_archival_usage_includes_frozen_networks_and_surfaces():
    from modules.agent.infra.database.network_agent_usage_reader import SQLAlchemyNetworkAgentUsageReader
    from types import SimpleNamespace

    project_id, agent_id, release_id = uuid4(), uuid4(), uuid4()
    network = {"type": "network", "id": "frozen-network", "name": "Frozen composition"}
    surface = {"type": "chat_surface", "id": "surface", "name": "Live chat"}
    networks = AsyncMock(return_value=[network])
    surfaces = AsyncMock(return_value=[surface])
    session = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [release_id])))
    reader = SQLAlchemyNetworkAgentUsageReader(SimpleNamespace(session=session), network_consumers=networks, surface_consumers=surfaces)
    assert await reader.list_draft_references(project_id=project_id, agent_id=agent_id) == [network, surface]
    networks.assert_awaited_once_with(project_id=project_id, agent_ids={str(agent_id)}, release_ids={str(release_id)})
    assert surfaces.await_args.kwargs["network_ids"] == {"frozen-network"}
