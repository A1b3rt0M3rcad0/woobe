from contextlib import asynccontextmanager
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.graph import composition_hash
from modules.network.infra.services import portable_export as module
from modules.network.infra.services.portable_export import PortableNetworkExportReader
from shared.contracts.errors import ConflictError, SnapshotCaptureConflict
from shared.security.principal import AuthenticatedPrincipal


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["binding", "constituent", "integrity", "none"])
async def test_network_capture_diagnoses_exact_closure_and_never_falls_back(
    monkeypatch, failure
):
    project, network_id, agent_id, node_id, snapshot_id, release_id = (
        uuid4() for _ in range(6)
    )
    definition = NetworkDefinition.from_dict(
        {
            "root_node_id": str(node_id),
            "nodes": [
                {
                    "id": str(node_id),
                    "agent_id": str(agent_id),
                    "label": "Support",
                    "binding": {"source": "release", "release_id": str(release_id)},
                }
            ],
            "edges": [],
            "settings": {},
        }
    )
    bindings = {
        str(node_id): {
            "release_id": str(release_id),
            "snapshot_override": {"model": "exact"},
        }
    }
    if failure == "binding":
        bindings = {}
    version = N(
        project_id=project,
        network_id=network_id,
        kind="release",
        id=snapshot_id,
        version="1.0.0",
        definition=definition.to_dict(),
        resolved_bindings=bindings,
        composition_hash="wrong"
        if failure == "integrity"
        else composition_hash(definition, bindings),
    )
    network = N(
        project_id=project,
        id=network_id,
        name="Support",
        description="",
        draft_revision=1,
    )
    session = N(
        bind=N(dialect=N(name="sqlite")),
        get=AsyncMock(side_effect=[network, version]),
        scalar=AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def begin():
        yield session

    authorizer = N(
        require_active_human=AsyncMock(),
        _project_workspace_id=AsyncMock(return_value=uuid4()),
        require_human_permission=AsyncMock(),
    )
    monkeypatch.setattr(module, "TenantAuthorizer", lambda _: authorizer)
    actor = object.__new__(AuthenticatedPrincipal)
    object.__setattr__(actor, "user_id", uuid4())
    agents = N(
        capture_in_session=AsyncMock(
            return_value={"source": {}, "definition": {"model": "exact"}}
        )
    )
    if failure == "constituent":
        agents.capture_in_session.side_effect = ConflictError(
            "protected-detail-not-for-client"
        )
    reader = PortableNetworkExportReader(
        N(begin=begin), N(_definition=NetworkDefinition.from_dict), agents
    )
    kwargs = dict(
        project_id=project,
        principal=actor,
        network_id=network_id,
        snapshot_id=snapshot_id,
    )
    if failure == "none":
        result = await reader.capture(**kwargs)
        assert result["spec"]["nodes"][0]["agent_ref"] == "agent-1"
        agents.capture_in_session.assert_awaited_once()
        assert agents.capture_in_session.await_args.kwargs["snapshot_id"] == release_id
        assert agents.capture_in_session.await_args.kwargs["source"] is None
    else:
        with pytest.raises(SnapshotCaptureConflict) as caught:
            await reader.capture(**kwargs)
        assert caught.value.code == "PACKAGE_EXPORT_NETWORK_" + failure.upper()
        assert caught.value.path.startswith("/spec")
        assert "protected-detail" not in str(caught.value)
        if failure != "constituent":
            agents.capture_in_session.assert_not_awaited()
