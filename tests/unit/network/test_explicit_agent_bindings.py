from uuid import UUID

import pytest

from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.graph import NetworkGraphError, validate_network_definition


ROOT_ID = "00000000-0000-4000-8000-000000000001"
AGENT_ID = "10000000-0000-4000-8000-000000000001"
RELEASE_ID = "20000000-0000-4000-8000-000000000001"


def definition_payload(*, binding=None, schema_version=1):
    node = {
        "id": ROOT_ID,
        "agent_id": AGENT_ID,
        "label": "Entry Agent",
        "capability_description": "Coordinates the request.",
        "position": {"x": 0, "y": 0},
    }
    if binding is not None:
        node["binding"] = binding
    return {
        "schema_version": schema_version,
        "root_node_id": ROOT_ID,
        "nodes": [node],
        "edges": [],
        "settings": {
            "session_mode": "stateful",
            "max_depth": 4,
            "max_invocations": 16,
            "timeout_seconds": 90,
        },
    }


def test_legacy_network_nodes_upgrade_to_explicit_draft_bindings():
    definition = NetworkDefinition.from_dict(definition_payload())

    assert definition.schema_version == 2
    assert definition.nodes[0].binding.source == "draft"
    assert definition.nodes[0].binding.release_id is None
    assert definition.to_dict()["nodes"][0]["binding"] == {
        "source": "draft",
        "release_id": None,
    }


def test_stable_binding_requires_exact_release_id():
    with pytest.raises(ValueError, match="requires release_id"):
        NetworkDefinition.from_dict(
            definition_payload(binding={"source": "staging", "release_id": None})
        )


def test_release_binding_preserves_exact_reference():
    definition = NetworkDefinition.from_dict(
        definition_payload(
            binding={"source": "release", "release_id": RELEASE_ID},
            schema_version=2,
        )
    )

    assert definition.nodes[0].binding.source == "release"
    assert definition.nodes[0].binding.release_id == UUID(RELEASE_ID)
    validate_network_definition(definition)


def test_invalid_binding_source_is_rejected():
    with pytest.raises(ValueError, match="draft, staging, release or candidate"):
        NetworkDefinition.from_dict(
            definition_payload(binding={"source": "latest", "release_id": RELEASE_ID})
        )


def test_graph_validation_rejects_a_draft_with_release_id():
    definition = NetworkDefinition.from_dict(definition_payload())
    object.__setattr__(definition.nodes[0].binding, "release_id", UUID(RELEASE_ID))

    with pytest.raises(NetworkGraphError, match="Draft Agent binding"):
        validate_network_definition(definition)


def test_exact_candidate_binding_cannot_enter_legacy_environments():
    from modules.network.domain.environment_bindings import validate_network_environment_bindings, NetworkEnvironmentBindingError
    definition = NetworkDefinition.from_dict(definition_payload(binding={"source": "candidate", "release_id": RELEASE_ID}))
    validate_network_definition(definition)
    validate_network_environment_bindings(definition, "candidate")
    for environment in ("draft", "staging", "production"):
        with pytest.raises(NetworkEnvironmentBindingError):
            validate_network_environment_bindings(definition, environment)
