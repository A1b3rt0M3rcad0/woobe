"""Turn a semantically validated closure into isolated preparation effects.

Candidate plans never reserve or advance a development registry binding. Native
root identities are read-only inputs; all executable snapshots are detached.
"""
from copy import deepcopy

from modules.package.domain.errors import PackageError


def isolate_candidate_plan(document, *, candidate_id, snapshot_ids, targets, source):
    plan = deepcopy(document)
    definitions = plan["source_definition"]["components"]
    entry = plan["source_definition"]["manifest"]["spec"]["entrypoint"]
    snapshot_keys = {key for key, component in definitions.items()
                     if component["kind"] in {"Agent", "Network"}}
    if set(snapshot_ids) != snapshot_keys or set(targets) != snapshot_keys:
        raise PackageError("ASAC_CANDIDATE_IDENTITY_INVALID", "Every native root needs an exact identity and snapshot")
    if any(not targets[key].get("resource_id") or targets[key].get("kind") != definitions[key]["kind"]
           for key in snapshot_keys):
        raise PackageError("ASAC_CANDIDATE_IDENTITY_INVALID", "Candidate preparation cannot create implicit Agent or Network roots")
    effects = []
    dependency_actions = {"resolve_model", "materialize_tool", "verify_mcp_discovery",
        "verify_mcp_readiness", "materialize_skill_version", "create_collection",
        "upload_document", "build_vector_snapshot", "verify_vector_snapshot",
        "create_prompt_version", "create_contract_version", "create_agent_knowledge_version"}
    for effect in plan["effects"]:
        action, key = effect["action"], effect["component"]
        if action in {"create_credential", "create_environment_value", "create_secret"}:
            raise PackageError("ASAC_CANDIDATE_BINDING_INVALID", "Bind existing protected resources before preparing a candidate")
        if action in {"prepare_inactive_agent", "prepare_network"}:
            effect.update(action="resolve_candidate_root", permission=definitions[key]["kind"].lower() + ":read")
            effect.pop("required_permissions", None)
            effects.append(effect)
        elif action in {"finalize_agent_draft", "save_network_draft"}:
            effect.update(action="create_candidate_snapshot", key="candidate:" + key,
                          permission=definitions[key]["kind"].lower() + ":version")
            effect.pop("required_permissions", None)
            effects.append(effect)
        elif action in dependency_actions:
            effects.append(effect)
        elif action == "verify_materialized_package":
            effect.update(action="verify_candidate_closure", permission=entry["kind"].lower() + ":version",
                          owner=entry["kind"].lower())
            effect.pop("required_permissions", None)
            effects.append(effect)
        elif action not in {"create_staging", "create_immutable_release", "activate_production", "verify_constituent_agent"}:
            raise PackageError("ASAC_CANDIDATE_PHASE_UNSUPPORTED", "Candidate preparation refuses an unclassified native effect")
    plan.update(mode="candidate", lifecycle="candidate", effects=effects,
        required_permissions=sorted({permission for effect in effects
            for permission in effect.get("required_permissions", [effect["permission"]])}),
        resource_bindings=deepcopy(targets),
        candidate={"candidate_id": str(candidate_id), "snapshot_ids": dict(snapshot_ids),
                   "source": deepcopy(source)})
    return plan
