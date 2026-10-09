"""Executable Network identity independent of lifecycle snapshot copy IDs.

Native composition_hash keeps its historical full-reference scope. This versioned
ASaC runtime identity retains topology, settings, exact constituent content hashes
and every frozen runtime override; only lifecycle selector metadata is excluded.
"""
from copy import deepcopy
from shared.contracts.asac import asac_digest

NETWORK_RUNTIME_SCOPE = "network-execution-runtime@2"
_BINDING_METADATA = {"release_id", "release_version", "release_status", "snapshot_kind",
    "binding_source", "snapshot_hash"}


def network_execution_payload(definition, bindings, external_context_contract):
    graph = deepcopy(definition.to_dict() if hasattr(definition, "to_dict") else definition)
    nodes = graph.get("nodes", [])
    if not nodes or not isinstance(bindings, dict) or set(bindings) != {str(node["id"]) for node in nodes}:
        raise ValueError("Network execution identity requires the complete frozen closure")
    closed = {}
    for node in nodes:
        binding = bindings[str(node["id"])]
        if (not isinstance(binding, dict) or binding.get("node_id") != str(node["id"])
            or binding.get("agent_id") != str(node["agent_id"])
            or not isinstance(binding.get("runtime_digest"), str)
            or len(binding["runtime_digest"]) != 71 or not binding["runtime_digest"].startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in binding["runtime_digest"][7:])
            or not isinstance(binding.get("snapshot_override"), dict)):
            raise ValueError("Network execution identity requires exact constituent runtime evidence")
        # AgentBindingSelector has exactly source/release_id. Unknown additions
        # must not silently vanish from a future execution contract.
        selector = node.get("binding")
        if not isinstance(selector, dict) or set(selector) != {"source", "release_id"}:
            raise ValueError("Unsupported Network lifecycle selector shape")
        node["binding"] = {"runtime_digest": binding["runtime_digest"]}
        closed[str(node["id"])] = {key: deepcopy(value) for key, value in binding.items() if key not in _BINDING_METADATA}
        # Native loaded_release_id remains the execution authority. This legacy
        # override field repeats that lifecycle selector, not executable content.
        closed[str(node["id"])]["snapshot_override"].pop("pinned_release_id", None)
    return {"schema_version": "2", "definition": graph, "bindings": closed,
        "external_context_contract": deepcopy(external_context_contract)}


def network_runtime_digest(definition, bindings, external_context_contract):
    return asac_digest("network-execution-runtime", network_execution_payload(definition, bindings, external_context_contract))
