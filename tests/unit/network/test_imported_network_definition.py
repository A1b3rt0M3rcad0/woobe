from uuid import uuid4

import pytest

from modules.network.application.portable_definition import (
    compile_imported_network_definition,
)
from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.graph import NetworkGraphError, validate_network_definition


def test_distinct_nodes_can_share_agent_without_losing_logical_keys_or_selectors():
    agent, staging, release, network = [uuid4() for _ in range(4)]
    spec = {
        "root": "support",
        "nodes": [
            {
                "key": "support",
                "agent_ref": "shared",
                "label": "Support",
                "binding": {"source": "staging"},
            },
            {
                "key": "review",
                "agent_ref": "shared",
                "label": "Review",
                "capability_description": "Review an answer",
                "binding": {"source": "release"},
            },
        ],
        "edges": [{"from": "support", "to": "review"}],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 3,
            "max_invocations": 7,
            "timeout_seconds": 60,
            "tool_result_max_chars": 7000,
        },
    }
    value = compile_imported_network_definition(
        spec,
        network_id=network,
        agents={"shared": agent},
        snapshots={"shared": {"staging": str(staging), "release": str(release)}},
    )
    definition = NetworkDefinition.from_dict(value)
    validate_network_definition(definition)
    assert len({node.id for node in definition.nodes}) == 2
    assert {node.agent_id for node in definition.nodes} == {agent}
    assert [node.portable_key for node in definition.nodes] == ["support", "review"]
    assert [node.binding.release_id for node in definition.nodes] == [staging, release]
    assert value["settings"] == spec["settings"]
    assert NetworkDefinition.from_dict(value).to_dict() == value
    assert (
        compile_imported_network_definition(
            spec,
            network_id=network,
            agents={"shared": agent},
            snapshots={"shared": {"staging": str(staging), "release": str(release)}},
        )
        == value
    )


def test_historical_networks_do_not_gain_portable_key_fields():
    identifier = uuid4()
    definition = NetworkDefinition.from_dict(
        {
            "root_node_id": str(identifier),
            "nodes": [
                {"id": str(identifier), "agent_id": str(uuid4()), "label": "Support"}
            ],
            "edges": [],
        }
    )
    assert "portable_key" not in definition.to_dict()["nodes"][0]


def test_invalid_or_duplicate_portable_keys_cannot_be_saved():
    root, child, agent = [uuid4() for _ in range(3)]
    value = {
        "root_node_id": str(root),
        "nodes": [
            {
                "id": str(root),
                "agent_id": str(agent),
                "label": "Root",
                "portable_key": "same",
            },
            {
                "id": str(child),
                "agent_id": str(agent),
                "label": "Child",
                "portable_key": "same",
            },
        ],
        "edges": [
            {
                "id": str(uuid4()),
                "source_node_id": str(root),
                "target_node_id": str(child),
            }
        ],
    }
    with pytest.raises(NetworkGraphError, match="portable node keys"):
        validate_network_definition(NetworkDefinition.from_dict(value))
    value["nodes"][1]["portable_key"] = "../unsafe"
    with pytest.raises(NetworkGraphError, match="portable node keys"):
        validate_network_definition(NetworkDefinition.from_dict(value))
