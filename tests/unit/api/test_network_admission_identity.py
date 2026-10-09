from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
from woobe_api.http.network.public_runtime import _execution_payload


def test_pinned_network_digest_excludes_current_selection_observations():
    session = SimpleNamespace(id=uuid4(), environment="production")
    execution = SimpleNamespace(id=uuid4(), project_id=uuid4(), network_id=uuid4(),
        network_version_id=uuid4(), definition_snapshot={"agents": ["frozen"]},
        resolved_bindings_snapshot={"agent": {"release": "fixed"}, "asac_run_identity": {"selection_relation": "matches_at_admission"}},
        status="completed", output_message="ok", parsed_output=None, output_parse_error=None,
        failure_code=None, root_trace_id=None, created_at=None, started_at=None, completed_at=None)
    original = deepcopy(execution.resolved_bindings_snapshot)
    first = _execution_payload(execution, session)["runtime_identity"]
    execution.resolved_bindings_snapshot["asac_run_identity"]["selection_relation"] = "pinned_snapshot"
    second = _execution_payload(execution, session)["runtime_identity"]
    assert first["admission_digest"] == second["admission_digest"]
    assert first["asac"] == original["asac_run_identity"]
    assert second["asac"]["selection_relation"] == "pinned_snapshot"
    execution.resolved_bindings_snapshot["agent"]["release"] = "different"
    assert _execution_payload(execution, session)["runtime_identity"]["admission_digest"] != first["admission_digest"]
