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
