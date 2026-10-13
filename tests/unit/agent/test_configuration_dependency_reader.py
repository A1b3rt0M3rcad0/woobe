"""Network compatibility overrides never replace the immutable Run closure."""
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database.configuration_dependency_reader import collect_configuration_dependencies
from shared.contracts.project_configuration import ConfigurationError


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [None, "stub", "incomplete"])
async def test_pinned_release_dependencies_win_over_network_override(override):
    project, agent, release, credential, node = (uuid4() for _ in range(5))
    row = N(id=release, agent_id=agent)
    provider = N(id=credential, project_id=project, provider="custom", binding_revision=4,
        authentication={"type":"api_key", "fields":{"api_key":{"source":"project_environment", "key":"PRIMARY"}}},
        meta={"base_url":"https://example.test/v1"}, status="active")
    session = N(scalars=AsyncMock(return_value=N(all=lambda:[row])),
        execute=AsyncMock(side_effect=[N(all=lambda:[provider]), N(all=lambda:[])]))
    binding = {"agent_id":str(agent), "release_id":str(release)}
    if override:
        binding["snapshot_override"] = {"provider":"custom", "model":"model"}
        if override == "stub":
            binding["snapshot_override"]["pinned_release_id"] = str(release)
    def snapshot_builder(value):
        assert value is row
        return {"provider_credential_id":str(credential)}
    dependencies = await collect_configuration_dependencies(session, project_id=project,
        bindings={str(node):binding}, snapshot_builder=snapshot_builder)
    assert len(dependencies) == 1
    assert dependencies[0].consumer_id == credential
    assert dependencies[0].key == "PRIMARY"
    assert dependencies[0].impact == (("network_node", str(node)),)
    session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_mismatched_pinned_identity_is_not_treated_as_free_snapshot():
    session = N(scalars=AsyncMock(), execute=AsyncMock())
    for release in (None, str(uuid4())):
        with pytest.raises(ConfigurationError) as error:
            await collect_configuration_dependencies(session, project_id=uuid4(),
                bindings={"node":{"release_id":release, "snapshot_override":{"pinned_release_id":str(uuid4())}}},
                snapshot_builder=lambda _: {})
        assert error.value.code == "CONFIG_BINDING_INVALID"
    session.scalars.assert_not_awaited()
    session.execute.assert_not_awaited()
