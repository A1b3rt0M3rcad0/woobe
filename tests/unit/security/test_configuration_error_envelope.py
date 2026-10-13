import json

import pytest
from starlette.requests import Request

from shared.contracts.project_configuration import ConfigurationError
from woobe_api.http.shared.errors import domain_error_handler


@pytest.mark.asyncio
@pytest.mark.parametrize("code,status", [
    ("CONFIG_VALUE_MISSING", 409), ("CONFIG_REVISION_CONFLICT", 409),
    ("CONFIG_USAGE_NOT_AUTHORIZED", 403), ("CONFIG_STORE_UNAVAILABLE", 503),
    ("CONFIG_BINDING_INVALID", 422),
])
async def test_configuration_errors_keep_safe_versioned_diagnostics_across_routes(code, status):
    request = Request({"type": "http", "method": "POST", "path": "/agents/id/deployments/apply", "headers": []})
    error = ConfigurationError(code, key="PRIMARY_API_KEY", environment="production")
    error.internal_provider_reply = "private-canary-never-in-response"
    response = await domain_error_handler(request, error)
    assert response.status_code == status
    body = json.loads(response.body)
    assert body["data"] == {"configuration_schema_version": "project_configuration.v1",
                            "diagnostics": [{"code": code, "key": "PRIMARY_API_KEY", "environment": "production"}]}
    assert body["meta"]["complete"] is False
    assert b"private-canary" not in response.body
