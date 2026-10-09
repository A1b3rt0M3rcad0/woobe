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


@pytest.mark.parametrize('plural,identifier',[('agents','agent_id'),('networks','network_id')])
@pytest.mark.parametrize('action',['acquire','renew','release','break'])
@pytest.mark.parametrize('scope,environment,suffix',[('resource','draft','write'),('draft','draft','write'),('staging','staging','version'),('production','production','production')])
def test_lease_permission_and_environment_come_from_validated_scope_not_query(plural,identifier,action,scope,environment,suffix):
    project,resource=str(uuid4()),str(uuid4())
    path=f'/projects/{project}/{plural}/{resource}/asac/leases/{action}'
    request=Request({'type':'http','method':'POST','path':path,'query_string':b'environment=draft&scope=draft','headers':[]})
    permission,params=resolve_operation('POST',path,{'scope':scope})
    assert permission==('project:access:write' if action=='break' else f'{plural[:-1]}:{suffix}')
    normalized=HttpSecurityGuard._authorization_path_params(request,params,{'scope':scope})
    assert normalized[identifier]==resource and normalized['environment']==environment
    assert resolve_operation('DELETE',path)[0] is None


@pytest.mark.parametrize('plural,identifier',[('agents','agent_id'),('networks','network_id')])
@pytest.mark.parametrize('scope,environment',[('resource','draft'),('draft','draft'),('staging','staging'),('production','production')])
def test_lease_reads_keep_exact_owner_scope(plural,identifier,scope,environment):
    path=f'/projects/{uuid4()}/{plural}/{uuid4()}/asac/leases'
    request=Request({'type':'http','method':'GET','path':path,'query_string':f'scope={scope}&environment=production'.encode(),'headers':[]})
    permission,params=resolve_operation('GET',path)
    assert permission==f'{plural[:-1]}:read'
    normalized=HttpSecurityGuard._authorization_path_params(request,params)
    assert identifier in normalized and normalized['environment']==environment


@pytest.mark.asyncio
@pytest.mark.parametrize('code,status',[('ASAC_LEASE_FENCED',409),('ASAC_LEASE_EXPIRED',409),('unexpected database failure',500)])
async def test_database_fencing_errors_never_echo_sql_author_or_protected_parameters(code,status,caplog):
    from sqlalchemy.exc import DBAPIError
    from woobe_api.http.shared.errors import database_exception_handler
    request=Request({'type':'http','method':'PUT','path':f'/projects/{uuid4()}/agents/{uuid4()}/asac/drafts/{uuid4()}','query_string':b'','headers':[]})
    error=DBAPIError('UPDATE private_table SET payload=:value',{'value':'private-provider-secret'},Exception(code+' private-provider-secret'),False)
    result=await database_exception_handler(request,error)
    assert result.status_code==status
    assert b'private-provider-secret' not in result.body and 'private-provider-secret' not in caplog.text
    assert b'private_table' not in result.body and 'private_table' not in caplog.text
    if status==409:
        assert code.encode() in result.body


@pytest.mark.parametrize('plural,identifier',[('agents','agent_id'),('networks','network_id')])
@pytest.mark.parametrize('suffix',['deployment-plans','deployments'])
@pytest.mark.parametrize('environment,permission',[('staging','version'),('production','production')])
def test_deployment_writes_cannot_spoof_environment_with_query(plural,identifier,suffix,environment,permission):
    project,resource=str(uuid4()),str(uuid4())
    path=f'/projects/{project}/{plural}/{resource}/asac/{suffix}'
    request=Request({'type':'http','method':'POST','path':path,'query_string':b'environment=draft','headers':[]})
    body={'environment':environment}
    allowed,params=resolve_operation('POST',path,body)
    assert allowed==f'{plural[:-1]}:{permission}'
    normalized=HttpSecurityGuard._authorization_path_params(request,params,body)
    assert normalized[identifier]==resource and normalized['environment']==environment
    assert resolve_operation('DELETE',path)[0] is None


@pytest.mark.parametrize("plural,mapped",[("agents","release_id"),("networks","network_version_id")])
def test_deployment_release_authorization_uses_exact_owner_table_without_changing_transport(plural,mapped):
    project,resource=str(uuid4()),str(uuid4())
    path=f"/projects/{project}/{plural}/{resource}/asac/deployment-plans"
    request=Request({"type":"http","method":"POST","path":path,"query_string":b"","headers":[]})
    body={"release_id":str(uuid4()),"environment":"production"}
    original=dict(body)
    normalized=HttpSecurityGuard._authorization_body(request,{"project_id":project,"resource_id":resource},body)
    assert normalized[mapped]==original["release_id"] and normalized["environment"]=="production"
    assert body==original
    if mapped!="release_id": assert "release_id" not in normalized
