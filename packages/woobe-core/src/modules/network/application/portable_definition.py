from uuid import NAMESPACE_URL, uuid5

from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.graph import validate_network_definition


def inspect_portable_network_definition(
    spec, *, hard_max_depth, hard_max_invocations, hard_timeout_seconds
):
    """Validate logical composition with native graph rules before IDs are materialized."""
    nodes = {
        node["key"]: uuid5(NAMESPACE_URL, "woobe-package-node:" + node["key"])
        for node in spec["nodes"]
    }
    native = {
        "root_node_id": str(nodes[spec["root"]]),
        "settings": spec.get("settings", {}),
        "nodes": [
            {
                "id": str(nodes[node["key"]]),
                "agent_id": str(
                    uuid5(NAMESPACE_URL, "woobe-package-agent:" + node["agent_ref"])
                ),
                "label": node.get("label", ""),
                "capability_description": node.get("capability_description", ""),
                "position": node.get("position", {}),
                "binding": {
                    "source": node.get("binding", {}).get("source", "draft"),
                    "release_id": str(
                        uuid5(NAMESPACE_URL, "woobe-package-binding:" + node["key"])
                    )
                    if node.get("binding", {}).get("source", "draft") != "draft"
                    else None,
                },
            }
            for node in spec["nodes"]
        ],
        "edges": [
            {
                "id": str(
                    uuid5(
                        NAMESPACE_URL, f"woobe-package-edge:{edge['from']}:{edge['to']}"
                    )
                ),
                "source_node_id": str(nodes[edge["from"]]),
                "target_node_id": str(nodes[edge["to"]]),
            }
            for edge in spec.get("edges", [])
        ],
    }
    definition = NetworkDefinition.from_dict(native)
    validate_network_definition(
        definition,
        hard_max_depth=hard_max_depth,
        hard_max_invocations=hard_max_invocations,
        hard_timeout_seconds=hard_timeout_seconds,
    )
    return {
        "settings": definition.to_dict()["settings"],
        "node_count": len(definition.nodes),
        "edge_count": len(definition.edges),
    }


def compile_imported_network_definition(spec, *, network_id, agents, snapshots):
    """Translate logical keys to native identities without changing graph semantics."""
    nodes = {
        node["key"]: uuid5(network_id, "node:" + node["key"]) for node in spec["nodes"]
    }
    native_nodes = []
    for node in spec["nodes"]:
        key = node["agent_ref"]
        source = node.get("binding", {}).get("source", "draft")
        native_nodes.append(
            {
                "id": str(nodes[node["key"]]),
                "portable_key": node["key"],
                "agent_id": str(agents[key]),
                "label": node.get("label", ""),
                "capability_description": node.get("capability_description", ""),
                "position": node.get("position", {}),
                "binding": {
                    "source": source,
                    "release_id": snapshots[key][source] if source != "draft" else None,
                },
            }
        )
    return NetworkDefinition.from_dict(
        {
            "root_node_id": str(nodes[spec["root"]]),
            "nodes": native_nodes,
            "settings": spec.get("settings", {}),
            "edges": [
                {
                    "id": str(uuid5(network_id, f"edge:{edge['from']}:{edge['to']}")),
                    "source_node_id": str(nodes[edge["from"]]),
                    "target_node_id": str(nodes[edge["to"]]),
                }
                for edge in spec.get("edges", [])
            ],
        }
    ).to_dict()
