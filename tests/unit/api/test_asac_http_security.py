from uuid import uuid4

import pytest
from starlette.requests import Request

from woobe_api.security.http_guard import HttpSecurityGuard
from woobe_api.security.operation_catalog import resolve_operation


@pytest.mark.parametrize("plural,identifier,permission", [("agents", "agent_id", "agent:read"), ("networks", "network_id", "network:read")])
@pytest.mark.parametrize("action,query,environment", [("current", b"environment=staging", "staging"), ("current", b"", "production"), ("history", b"environment=staging", "production")])
def test_asac_reads_have_reviewed_target_and_verified_environment(plural, identifier, permission, action, query, environment):
    project, resource = str(uuid4()), str(uuid4())
    path = f"/projects/{project}/{plural}/{resource}/asac/{action}"
    request = Request({"type": "http", "method": "GET", "path": path, "query_string": query, "headers": []})
    allowed, params = resolve_operation("GET", path)
    assert allowed == permission
    normalized = HttpSecurityGuard._authorization_path_params(request, params)
    assert normalized == {"project_id": project, identifier: resource, "environment": environment}
    assert resolve_operation("POST", path)[0] is None
    assert resolve_operation("GET", path + "/unknown")[0] is None


@pytest.mark.parametrize("plural,identifier", [("agents", "agent_id"), ("networks", "network_id")])
@pytest.mark.parametrize("method,suffix,permission", [("POST", "drafts", "write"), ("PUT", "drafts/{draft_id}", "write"), ("POST", "revisions", "write"), ("GET", "operations/{operation_id}", "read")])
def test_asac_draft_routes_are_explicitly_scoped(plural, identifier, method, suffix, permission):
    project, resource = str(uuid4()), str(uuid4())
    suffix = suffix.format(draft_id=uuid4(), operation_id=uuid4())
    path = f"/projects/{project}/{plural}/{resource}/asac/{suffix}"
    request = Request({"type": "http", "method": method, "path": path,
        "query_string": b"environment=production", "headers": []})
    allowed, params = resolve_operation(method, path)
    assert allowed == f"{plural[:-1]}:{permission}"
    normalized = HttpSecurityGuard._authorization_path_params(request, params)
    assert normalized[identifier] == resource and normalized["environment"] == "draft"
    assert "resource_id" not in normalized
    assert resolve_operation("DELETE", path)[0] is None


@pytest.mark.asyncio
async def test_asac_invalid_request_does_not_echo_author_or_unknown_fields():
    from fastapi.exceptions import RequestValidationError
    from woobe_api.http.shared.errors import request_validation_handler
    request = Request({"type":"http","method":"POST","path":f"/projects/{uuid4()}/agents/{uuid4()}/asac/revisions","query_string":b"","headers":[]})
    error = RequestValidationError([{"type":"value_error","loc":("body","record"),"input":{"message":"private-provider-secret"}}])
    result = await request_validation_handler(request,error)
    assert result.status_code == 422
    assert b"ASAC_REQUEST_INVALID" in result.body
    assert b"private-provider-secret" not in result.body


@pytest.mark.parametrize("plural,identifier", [("agents", "agent_id"), ("networks", "network_id")])
@pytest.mark.parametrize("method,suffix,permission", [("POST", "candidates", "version"), ("GET", "candidates/{candidate_id}", "read")])
def test_candidate_routes_use_staging_authority_even_with_forged_environment(plural, identifier, method, suffix, permission):
    project, resource = str(uuid4()), str(uuid4())
    path = f"/projects/{project}/{plural}/{resource}/asac/" + suffix.format(candidate_id=uuid4())
    request = Request({"type": "http", "method": method, "path": path, "query_string": b"environment=production", "headers": []})
    allowed, params = resolve_operation(method, path)
    assert allowed == f"{plural[:-1]}:{permission}"
    normalized = HttpSecurityGuard._authorization_path_params(request, params)
    assert normalized[identifier] == resource and normalized["environment"] == "staging"
    assert resolve_operation("DELETE", path)[0] is None


@pytest.mark.parametrize("plural,identifier", [("agents", "agent_id"), ("networks", "network_id")])
@pytest.mark.parametrize("method,suffix,permission", [
    ("POST", "candidates/{candidate_id}/evaluations", "run:execute"),
    ("GET", "evaluations/{evaluation_id}", "run:read"),
    ("POST", "evaluations/{evaluation_id}/reconcile", "run:execute"),
])
def test_evaluation_routes_cannot_escalate_environment_or_omit_native_scope(plural, identifier, method, suffix, permission):
    project, resource = str(uuid4()), str(uuid4())
    path = f"/projects/{project}/{plural}/{resource}/asac/" + suffix.format(candidate_id=uuid4(),evaluation_id=uuid4())
    request = Request({"type":"http","method":method,"path":path,"query_string":b"environment=production","headers":[]})
    allowed, params = resolve_operation(method,path)
    assert allowed == permission
    normalized = HttpSecurityGuard._authorization_path_params(request,params)
    assert normalized[identifier] == resource and normalized["project_id"] == project
    assert normalized["environment"] == "staging" and "resource_id" not in normalized
    assert resolve_operation("DELETE",path)[0] is None


@pytest.mark.parametrize("plural,identifier", [("agents", "agent_id"), ("networks", "network_id")])
@pytest.mark.parametrize("method,suffix,permission", [("POST","publications","version"),("GET","publications/{publication_id}","read")])
def test_exact_publication_routes_use_saved_candidate_authority(plural,identifier,method,suffix,permission):
    project,resource=str(uuid4()),str(uuid4())
    path=f"/projects/{project}/{plural}/{resource}/asac/"+suffix.format(publication_id=uuid4())
    request=Request({"type":"http","method":method,"path":path,"query_string":b"environment=production","headers":[]})
    allowed,params=resolve_operation(method,path)
    assert allowed==f"{plural[:-1]}:{permission}"
    normalized=HttpSecurityGuard._authorization_path_params(request,params)
    assert normalized[identifier]==resource and normalized["environment"]=="staging"
    assert resolve_operation("DELETE",path)[0] is None


@pytest.mark.parametrize("action", ["reconcile", "cancel"])
def test_network_publication_recovery_requires_version_authority(action):
    project,resource=str(uuid4()),str(uuid4())
    path=f"/projects/{project}/networks/{resource}/asac/publications/{uuid4()}/{action}"
    request=Request({"type":"http","method":"POST","path":path,"query_string":b"environment=production","headers":[]})
    permission,params=resolve_operation("POST",path)
    assert permission=="network:version"
    normalized=HttpSecurityGuard._authorization_path_params(request,params)
    assert normalized["network_id"]==resource and normalized["project_id"]==project and normalized["environment"]=="staging"
    for method in ("GET","PUT","DELETE"):
        assert resolve_operation(method,path)[0] is None
    assert resolve_operation("POST",path.replace("/networks/","/agents/"))[0] is None
