import inspect

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from modules.agent import entrypoint
from woobe_api.http.agent import routes
from woobe_api.http.shared.openapi_contracts import request_body_contract


CONTRACTS = [
    ('create_agent', 'CreateAgentInput', '/ai/agents', 'post'),
    ('update_agent', 'UpdateAgentInput', '/ai/agents/{agent_id}', 'patch'),
]


@pytest.mark.parametrize("endpoint,model_name,path,method", CONTRACTS)
def test_agent_input_schema_uses_the_same_public_dto(endpoint, model_name, path, method):
    app = FastAPI()
    app.include_router(routes.router)
    model = getattr(entrypoint, model_name)
    expected = request_body_contract(model, path, method, required=method != "patch")
    operation = app.openapi()["paths"][path][method]
    assert operation["requestBody"] == jsonable_encoder(expected["requestBody"], exclude_none=True)
    assert list(inspect.signature(getattr(routes, endpoint)).parameters) == ["request"]
