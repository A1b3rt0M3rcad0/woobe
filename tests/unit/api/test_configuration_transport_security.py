import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from starlette.requests import Request

from woobe_api.http.shared.errors import pydantic_validation_handler, request_validation_handler

CANARY = "private-material-do-not-echo"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/ai/provider-credentials", "/ai/tools", "/core/projects/id/configuration/value-batches"])
async def test_rejected_material_never_appears_in_request_validation_response(path):
    request = Request({"type": "http", "method": "POST", "path": path, "headers": [], "query_string": b""})
    error = RequestValidationError([{"type": "value_error", "loc": ("body", CANARY),
        "input": {"value": CANARY}, "msg": CANARY, "ctx": {"error": CANARY}}])
    response = await request_validation_handler(request, error)
    assert response.status_code == 422
    assert CANARY.encode() not in response.body


@pytest.mark.asyncio
async def test_application_validation_never_echoes_credentials():
    class Body(BaseModel):
        secret: int
    with pytest.raises(ValidationError) as failure:
        Body(secret=CANARY)
    response = await pydantic_validation_handler(None, failure.value)
    assert response.status_code == 422
    assert CANARY.encode() not in response.body
