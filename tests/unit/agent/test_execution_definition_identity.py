from copy import deepcopy
from types import SimpleNamespace

import pytest

from modules.agent.domain.execution_definition import (
    AGENT_EXECUTION_FIELDS,
    AgentExecutionSnapshot,
    hash_agent_execution_snapshot,
)
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)


@pytest.mark.parametrize(
    "field",
    [
        "external_context_contract",
        "model_spec_snapshot",
        "model_spec_hash",
        "fallback_model_spec_snapshot",
        "fallback_model_spec_hash",
    ],
)
def test_v2_identity_covers_previously_omitted_executable_fields(field):
    source = SimpleNamespace(name="support", runtime_config={})
    changed = deepcopy(source)
    setattr(
        changed,
        field,
        {"different": True}
        if field.endswith("snapshot") or field.endswith("contract")
        else "different",
    )
    # Legacy receipt material stays stable; new equivalence must not collapse it.
    assert release_snapshot_hash(source) == release_snapshot_hash(changed)
    assert hash_agent_execution_snapshot(source) != hash_agent_execution_snapshot(
        changed
    )
    assert not release_snapshots_equal(source, changed)


def test_snapshot_is_versioned_and_preserves_every_execution_field():
    source = {field: f"value-{field}" for field in AGENT_EXECUTION_FIELDS}
    source["collection_ids"] = ["b", "a"]
    source["runtime_config"] = {"execution_strategy": "standard"}
    snapshot = AgentExecutionSnapshot.from_source(source)
    assert snapshot.schema_version == "2"
    assert set(snapshot.definition.fields) == set(AGENT_EXECUTION_FIELDS)
    assert snapshot.definition.fields["collection_ids"] == ["a", "b"]
    assert source["collection_ids"] == ["b", "a"]


def test_dictionary_order_and_collection_order_do_not_change_identity():
    left = {"collection_ids": ["a", "b"], "runtime_config": {"x": 1, "y": 2}}
    right = {"runtime_config": {"y": 2, "x": 1}, "collection_ids": ["b", "a"]}
    assert hash_agent_execution_snapshot(left) == hash_agent_execution_snapshot(right)


def test_nonfinite_executable_numbers_are_not_hashable():
    with pytest.raises(ValueError):
        hash_agent_execution_snapshot({"temperature": float("nan")})
