from copy import deepcopy
from uuid import uuid4
import pytest
from modules.network.domain.execution_identity import network_runtime_digest


def closure():
    node, agent, snapshot = (str(uuid4()) for _ in range(3))
    definition = {"root_node_id": node, "nodes": [{"id": node, "agent_id": agent,
        "label": "Support", "binding": {"source": "candidate", "release_id": snapshot}}],
        "edges": [], "settings": {"session_mode": "stateless"}}
    bindings = {node: {"node_id": node, "agent_id": agent, "release_id": snapshot,
        "release_version": "candidate", "release_status": "archived", "snapshot_kind": "candidate",
        "binding_source": "candidate", "snapshot_hash": "legacy-metadata-hash",
        "runtime_digest": "sha256:" + "d" * 64, "session_mode": "stateless",
        "snapshot_override": {"provider": "custom", "model": "exact", "temperature": 0.5, "pinned_release_id": snapshot}}}
    return node, definition, bindings


def test_lifecycle_copy_keeps_exact_runtime_but_changed_content_does_not():
    node, original, bindings = closure()
    before = network_runtime_digest(original, bindings, None)
    published, copied = deepcopy(original), deepcopy(bindings)
    new = str(uuid4())
    published["nodes"][0]["binding"] = {"source": "release", "release_id": new}
    copied[node].update(release_id=new, release_version="v0.0.20261009.01",
        release_status="released", snapshot_kind="release", binding_source="release", snapshot_hash="new-metadata-hash")
    copied[node]["snapshot_override"]["pinned_release_id"] = new
    assert network_runtime_digest(published, copied, None) == before
    for field, value in (("runtime_digest", "sha256:" + "e" * 64),
        ("snapshot_override", {"provider": "custom", "model": "different"}),
        ("session_mode", "stateful"), ("future_execution_field", True)):
        changed = deepcopy(copied)
        changed[node][field] = value
        assert network_runtime_digest(published, changed, None) != before
    assert network_runtime_digest(published, copied, {"required": ["tenant"]}) != before
    published["nodes"][0]["label"] = "Different routing label"
    assert network_runtime_digest(published, copied, None) != before


def test_execution_identity_rejects_missing_or_unsupported_closure():
    node, definition, bindings = closure()
    for corrupted in ({}, {node: {**bindings[node], "runtime_digest": "unverified"}},
        {node: {**bindings[node], "agent_id": str(uuid4())}}):
        with pytest.raises(ValueError):
            network_runtime_digest(definition, corrupted, None)
    definition["nodes"][0]["binding"]["future_selector"] = "not ignored"
    with pytest.raises(ValueError):
        network_runtime_digest(definition, bindings, None)
