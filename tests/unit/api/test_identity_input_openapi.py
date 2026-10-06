import inspect

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from modules.identity.entrypoint import CreateWorkspaceInput, LoginInput, RegisterInput
from woobe_api.http.identity import routes
from woobe_api.http.shared.openapi_contracts import request_body_contract


@pytest.mark.parametrize("path,endpoint,model", [
    ("/identity/auth/login", "login", LoginInput),
    ("/identity/auth/register", "register", RegisterInput),
    ("/identity/workspaces", "create_workspace", CreateWorkspaceInput),
])
def test_identity_body_contract_keeps_authorization_and_cookie_dispatch(path, endpoint, model):
    app = FastAPI()
    app.include_router(routes.router)
    expected = request_body_contract(model, path, "post")
    assert app.openapi()["paths"][path]["post"]["requestBody"] == jsonable_encoder(expected["requestBody"], exclude_none=True)
    assert list(inspect.signature(getattr(routes, endpoint)).parameters) == ["request"]


def test_workspace_update_advertises_existing_dto_and_retains_admin_dispatch():
    from modules.identity.entrypoint import UpdateWorkspaceInput
    app = FastAPI()
    app.include_router(routes.router)
    path = "/identity/workspaces/{workspace_id}"
    expected = request_body_contract(UpdateWorkspaceInput, path, "patch")
    assert app.openapi()["paths"][path]["patch"]["requestBody"] == jsonable_encoder(expected["requestBody"], exclude_none=True)
    assert list(inspect.signature(routes.update_workspace).parameters) == ["request", "workspace_id"]
    assert "requestBody" not in app.openapi()["paths"]["/identity/workspaces/{workspace_id}/members"]["post"]
