from copy import deepcopy
from uuid import uuid4

import pytest

from modules.package.application.candidate_planning import isolate_candidate_plan
from modules.package.domain.errors import PackageError


def test_network_candidate_strips_all_singleton_and_publication_effects():
    document = {"source_definition": {"manifest": {"spec": {"entrypoint": {"kind": "Network", "ref": "root"}}},
        "components": {"root": {"kind": "Network"}, "node": {"kind": "Agent"}}},
        "effects": [{"key": action, "component": component, "action": action,
            "permission": "network:write", "owner": "network", "state": "materializing"}
            for action, component in [("prepare_inactive_agent", "node"), ("finalize_agent_draft", "node"),
                ("create_staging", "node"), ("create_immutable_release", "node"), ("prepare_network", "root"),
                ("save_network_draft", "root"), ("activate_production", "root"), ("verify_materialized_package", "root")]]}
    original = deepcopy(document)
    plan = isolate_candidate_plan(document, candidate_id=uuid4(),
        snapshot_ids={key: str(uuid4()) for key in ("root", "node")},
        targets={key: {"kind": kind, "resource_id": str(uuid4())} for key, kind in [("root", "Network"), ("node", "Agent")]}, source={})
    assert document == original
    assert [effect["action"] for effect in plan["effects"]] == ["resolve_candidate_root", "create_candidate_snapshot",
        "resolve_candidate_root", "create_candidate_snapshot", "verify_candidate_closure"]
    assert "network:production" not in plan["required_permissions"]
    assert plan["lifecycle"] == "candidate"
    document["effects"].insert(0, {"action": "create_secret", "component": "secret"})
    with pytest.raises(PackageError, match="existing protected"):
        isolate_candidate_plan(document, candidate_id=uuid4(), snapshot_ids=plan["candidate"]["snapshot_ids"],
            targets=plan["resource_bindings"], source={})
