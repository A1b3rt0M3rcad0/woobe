from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.execution_identity import NETWORK_RUNTIME_SCOPE, network_runtime_digest
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.services.asac_native_publisher import NetworkASaCNativePublisher
from shared.contracts.errors import ConflictError


def frozen_closure():
    project, root, agent, node, snapshot, child_snapshot = (uuid4() for _ in range(6))
    definition = NetworkDefinition.from_dict({"root_node_id": str(node), "nodes": [{"id": str(node),
        "agent_id": str(agent), "label": "Support", "binding": {"source": "candidate", "release_id": str(child_snapshot)}}],
        "edges": [], "settings": {"session_mode": "stateless"}}).to_dict()
    bindings = {str(node): {"node_id": str(node), "agent_id": str(agent), "release_id": str(child_snapshot),
        "release_version": child_snapshot.hex, "release_status": "archived", "snapshot_kind": "candidate", "binding_source": "candidate",
        "snapshot_hash": "legacy", "runtime_digest": "sha256:" + "d" * 64, "session_mode": "stateless",
        "snapshot_override": {"provider": "custom", "model": "frozen", "pinned_release_id": str(child_snapshot), "external_context_contract": None}}}
    source = NetworkVersionModel(id=snapshot, project_id=project, network_id=root, kind="candidate",
        version=snapshot.hex, definition=definition, resolved_bindings=bindings, effective_external_context_contract=None,
        composition_hash=composition_hash(NetworkDefinition.from_dict(definition), bindings))
    candidate = N(root_snapshot_id=snapshot, native_bindings=deepcopy(bindings), runtime_digest_scope=NETWORK_RUNTIME_SCOPE,
        runtime_digest=network_runtime_digest(definition, bindings, None), record_digest="sha256:" + "c" * 64)
    receipt = {"project_id": str(project), "resource_id": str(agent), "source_snapshot_id": str(child_snapshot),
        "release_id": str(uuid4()), "release_version": "v0.0.20261009.01", "release_status": "released",
        "runtime_digest": bindings[str(node)]["runtime_digest"], "complete": True,
        "release_snapshot": {"provider": "custom", "model": "frozen", "external_context_contract": None,
            "response_format": {}, "output_schema": None}}
    children = {str(node): receipt}
    root_model = NetworkModel(id=root, project_id=project, production_version_id=None, staging_version_id=uuid4())
    releases, added = [], []

    async def get(model, identity):
        return source if model is NetworkVersionModel and identity == snapshot else root_model if model is NetworkModel else None

    session = N(get=AsyncMock(side_effect=get), scalars=AsyncMock(side_effect=lambda query: N(all=lambda: releases)),
        add=lambda row: added.append(row), flush=AsyncMock())
    return project, root, source, candidate, children, root_model, releases, added, session


@pytest.mark.asyncio
async def test_exact_network_publication_translates_storage_ids_without_retargeting_runtime():
    project, root, source, candidate, children, root_model, releases, added, session = frozen_closure()
    publisher = NetworkASaCNativePublisher()
    captured = await publisher.capture(session=session, project_id=project, resource_id=root, candidate=candidate)
    original = deepcopy(source.definition), deepcopy(source.resolved_bindings), root_model.staging_version_id
    args = dict(session=session, project_id=project, resource_id=root, candidate=candidate,
        principal=N(), reason="Qualified exact Network", source=captured, children=children)
    result = await publisher.publish(**args)
    assert not result["reused"] and result["runtime_digest"] == candidate.runtime_digest
    published = added[0]
    assert published.kind == "release" and published.id != source.id
    assert published.definition["nodes"][0]["binding"]["source"] == "release"
    assert published.composition_hash != source.composition_hash
    assert network_runtime_digest(published.definition, published.resolved_bindings, published.effective_external_context_contract) == candidate.runtime_digest
    assert published.source_version_id == source.id and published.source_staging_version_id is None
    assert published.entry_agent_release_id and published.agent_release_manifest and published.release_fingerprint
    assert (source.definition, source.resolved_bindings, root_model.staging_version_id) == original
    assert root_model.production_version_id is None and source.kind == "candidate"
    releases.append(published)
    reused = await publisher.publish(**args)
    assert reused["reused"] and reused["release_id"] == published.id and len(added) == 1


@pytest.mark.asyncio
async def test_network_publication_refuses_missing_or_changed_constituent_proof():
    project, root, source, candidate, children, root_model, releases, added, session = frozen_closure()
    publisher = NetworkASaCNativePublisher()
    captured = await publisher.capture(session=session, project_id=project, resource_id=root, candidate=candidate)
    args = dict(session=session, project_id=project, resource_id=root, candidate=candidate,
        principal=N(), reason="Qualified exact Network", source=captured)
    with pytest.raises(ConflictError, match="PREPARATION_INCOMPLETE"):
        await publisher.publish(**args, children={})
    wrong = deepcopy(children)
    next(iter(wrong.values()))["release_snapshot"]["model"] = "other"
    with pytest.raises(ConflictError, match="executable override differs"):
        await publisher.publish(**args, children=wrong)
    wrong = deepcopy(children)
    next(iter(wrong.values()))["runtime_digest"] = "sha256:" + "e" * 64
    with pytest.raises(ConflictError, match="copy proof differs"):
        await publisher.publish(**args, children=wrong)
    assert added == []
    candidate.runtime_digest_scope = None
    with pytest.raises(ConflictError, match="RUNTIME_SCOPE_INCOMPATIBLE"):
        await publisher.capture(session=session, project_id=project, resource_id=root, candidate=candidate)
