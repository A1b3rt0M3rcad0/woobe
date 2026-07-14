from uuid import uuid4

import pytest

from modules.network.domain.entities import (
    NetworkDefinition,
    NetworkEdge,
    NetworkLimits,
    NetworkNode,
)
from modules.network.domain.graph import (
    NetworkGraphError,
    composition_hash,
    delegation_tool_name,
    validate_network_definition,
)


def definition() -> NetworkDefinition:
    root = NetworkNode(
        id=uuid4(),
        agent_id=uuid4(),
        label="Coordinator",
        capability_description="Routes work to the right specialist.",
    )
    child = NetworkNode(
        id=uuid4(),
        agent_id=uuid4(),
        label="Billing specialist",
        capability_description="Investigates invoices and billing disputes.",
    )
    return NetworkDefinition(
        root_node_id=root.id,
        nodes=(root, child),
        edges=(
            NetworkEdge(
                id=uuid4(),
                source_node_id=root.id,
                target_node_id=child.id,
            ),
        ),
        limits=NetworkLimits(max_depth=4, max_invocations=16, timeout_seconds=90),
    )


def test_validates_reachable_single_root_graph() -> None:
    validate_network_definition(definition())


def test_rejects_root_as_delegation_target() -> None:
    graph = definition()
    child = graph.nodes[1]
    graph = NetworkDefinition(
        root_node_id=graph.root_node_id,
        nodes=graph.nodes,
        edges=graph.edges
        + (
            NetworkEdge(
                id=uuid4(),
                source_node_id=child.id,
                target_node_id=graph.root_node_id,
            ),
        ),
        limits=graph.limits,
    )
    with pytest.raises(NetworkGraphError, match="root Agent"):
        validate_network_definition(graph)


def test_rejects_unreachable_agent() -> None:
    graph = definition()
    orphan = NetworkNode(id=uuid4(), agent_id=uuid4(), label="Orphan")
    graph = NetworkDefinition(
        root_node_id=graph.root_node_id,
        nodes=graph.nodes + (orphan,),
        edges=graph.edges,
        limits=graph.limits,
    )
    with pytest.raises(NetworkGraphError, match="reachable"):
        validate_network_definition(graph)


def test_rejects_delegation_cycle_below_root() -> None:
    graph = definition()
    child = graph.nodes[1]
    grandchild = NetworkNode(id=uuid4(), agent_id=uuid4(), label="Refund specialist")
    graph = NetworkDefinition(
        root_node_id=graph.root_node_id,
        nodes=graph.nodes + (grandchild,),
        edges=graph.edges
        + (
            NetworkEdge(
                id=uuid4(),
                source_node_id=child.id,
                target_node_id=grandchild.id,
            ),
            NetworkEdge(
                id=uuid4(),
                source_node_id=grandchild.id,
                target_node_id=child.id,
            ),
        ),
        limits=graph.limits,
    )
    with pytest.raises(NetworkGraphError, match="cycles"):
        validate_network_definition(graph)


def test_enforces_hard_limits() -> None:
    graph = definition()
    graph = NetworkDefinition(
        root_node_id=graph.root_node_id,
        nodes=graph.nodes,
        edges=graph.edges,
        limits=NetworkLimits(max_depth=9, max_invocations=16, timeout_seconds=90),
    )
    with pytest.raises(NetworkGraphError, match="max_depth"):
        validate_network_definition(graph)


def test_tool_names_are_stable_and_safe() -> None:
    node = NetworkNode(id=uuid4(), agent_id=uuid4(), label="Billing & Refunds")
    assert delegation_tool_name(node) == "delegate_to_billing_refunds"


def test_composition_hash_changes_with_exact_release_binding() -> None:
    graph = definition()
    first = composition_hash(graph, {str(graph.root_node_id): {"release_id": "a"}})
    second = composition_hash(graph, {str(graph.root_node_id): {"release_id": "b"}})
    assert first != second


def test_composition_hash_versions_delegation_capabilities() -> None:
    graph = definition()
    changed_child = NetworkNode(
        id=graph.nodes[1].id,
        agent_id=graph.nodes[1].agent_id,
        label=graph.nodes[1].label,
        capability_description="Handles refunds only.",
        position=graph.nodes[1].position,
    )
    changed = NetworkDefinition(
        root_node_id=graph.root_node_id,
        nodes=(graph.nodes[0], changed_child),
        edges=graph.edges,
        limits=graph.limits,
    )
    bindings = {str(graph.root_node_id): {"release_id": "a"}}

    assert composition_hash(graph, bindings) != composition_hash(changed, bindings)
