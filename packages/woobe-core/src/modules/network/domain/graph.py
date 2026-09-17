from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID

from modules.network.domain.entities import NetworkDefinition, NetworkNode


class NetworkGraphError(ValueError):
    pass


def validate_network_definition(
    definition: NetworkDefinition,
    *,
    hard_max_depth: int = 8,
    hard_max_invocations: int = 64,
    hard_timeout_seconds: int = 300,
    hard_tool_result_max_chars: int = 64_000,
) -> None:
    if definition.schema_version != 2:
        raise NetworkGraphError("Unsupported Network definition schema version")
    if not definition.nodes:
        raise NetworkGraphError("Network must contain at least one Agent node")

    nodes = {node.id: node for node in definition.nodes}
    if len(nodes) != len(definition.nodes):
        raise NetworkGraphError("Network node ids must be unique")
    if definition.root_node_id not in nodes:
        raise NetworkGraphError("Network must have exactly one valid root Agent")
    if definition.session_mode not in {"stateful", "stateless"}:
        raise NetworkGraphError("Network session_mode must be stateful or stateless")

    edge_ids: set[UUID] = set()
    edges: set[tuple[UUID, UUID]] = set()
    reachable: dict[UUID, list[UUID]] = {node_id: [] for node_id in nodes}
    for edge in definition.edges:
        if edge.id in edge_ids:
            raise NetworkGraphError("Network edge ids must be unique")
        edge_ids.add(edge.id)
        if edge.source_node_id not in nodes or edge.target_node_id not in nodes:
            raise NetworkGraphError("Network edges must reference existing Agent nodes")
        if edge.source_node_id == edge.target_node_id:
            raise NetworkGraphError("An Agent cannot delegate directly to itself")
        if edge.target_node_id == definition.root_node_id:
            raise NetworkGraphError("The root Agent cannot be a delegation target")
        key = (edge.source_node_id, edge.target_node_id)
        if key in edges:
            raise NetworkGraphError("Duplicate delegation edge")
        edges.add(key)
        reachable[edge.source_node_id].append(edge.target_node_id)

    visited: set[UUID] = set()
    pending = [definition.root_node_id]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(reachable[current])
    unreachable = set(nodes) - visited
    if unreachable:
        raise NetworkGraphError("Every Agent node must be reachable from the root Agent")

    visiting: set[UUID] = set()
    visited_for_cycles: set[UUID] = set()

    def visit_for_cycles(node_id: UUID) -> None:
        if node_id in visiting:
            raise NetworkGraphError("Network delegation graph cannot contain cycles")
        if node_id in visited_for_cycles:
            return
        visiting.add(node_id)
        for target_id in reachable[node_id]:
            visit_for_cycles(target_id)
        visiting.remove(node_id)
        visited_for_cycles.add(node_id)

    visit_for_cycles(definition.root_node_id)

    limits = definition.limits
    if not 1 <= limits.max_depth <= hard_max_depth:
        raise NetworkGraphError(f"max_depth must be between 1 and {hard_max_depth}")
    if not 1 <= limits.max_invocations <= hard_max_invocations:
        raise NetworkGraphError(f"max_invocations must be between 1 and {hard_max_invocations}")
    if not 1 <= limits.timeout_seconds <= hard_timeout_seconds:
        raise NetworkGraphError(f"timeout_seconds must be between 1 and {hard_timeout_seconds}")
    if not 1_000 <= limits.tool_result_max_chars <= hard_tool_result_max_chars:
        raise NetworkGraphError(
            f"tool_result_max_chars must be between 1000 and {hard_tool_result_max_chars}"
        )

    names: set[str] = set()
    for node in definition.nodes:
        if len(node.capability_description) > 2000:
            raise NetworkGraphError("Agent capability_description cannot exceed 2000 characters")
        if node.binding.source == "draft" and node.binding.release_id is not None:
            raise NetworkGraphError("Draft Agent binding cannot include release_id")
        if node.binding.source != "draft" and node.binding.release_id is None:
            raise NetworkGraphError(f"{node.binding.source.title()} Agent binding requires release_id")
        name = delegation_tool_name(node)
        if name in names:
            raise NetworkGraphError("Agent labels must generate unique delegation tool names")
        names.add(name)


def delegation_tool_name(node: NetworkNode) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", node.label.strip().lower().replace("-", "_"))
    slug = re.sub(r"_+", "_", slug).strip("_") or f"agent_{str(node.id)[:8]}"
    if slug[0].isdigit():
        slug = f"agent_{slug}"
    return f"delegate_to_{slug}"[:64]


def composition_hash(definition: NetworkDefinition, resolved_bindings: dict[str, object]) -> str:
    payload = {
        "definition": definition.to_dict(),
        "resolved_bindings": resolved_bindings,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
