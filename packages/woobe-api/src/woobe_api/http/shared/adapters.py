from typing import Any

from fastapi import Request as FastAPIRequest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)


_STATUS_BY_OUTCOME = {
    OperationOutcome.SUCCESS: 200,
    OperationOutcome.CREATED: 201,
    OperationOutcome.ACCEPTED: 202,
    OperationOutcome.INVALID: 400,
    OperationOutcome.UNAUTHENTICATED: 401,
    OperationOutcome.FORBIDDEN: 403,
    OperationOutcome.NOT_FOUND: 404,
    OperationOutcome.CONFLICT: 409,
    OperationOutcome.UNPROCESSABLE: 422,
    OperationOutcome.FAILURE: 500,
    OperationOutcome.NOT_IMPLEMENTED: 501,
    OperationOutcome.UPSTREAM_FAILURE: 502,
}


async def request_adapter(
    fastapi_request: FastAPIRequest,
    handler: Any,
    *,
    metadata: dict[str, Any] | None = None,
) -> OperationResult:
    body: Any = None
    try:
        body = await fastapi_request.json()
    except Exception:
        body = None

    principal = getattr(fastapi_request.state, "principal", None)
    operation_request = OperationRequest(
        principal=principal,
        body=body,
        query_params=dict(fastapi_request.query_params),
        path_params=dict(fastapi_request.path_params),
        metadata=dict(metadata or {}),
    )

    response = await handler(operation_request)
    return response


def response_adapter(response: OperationResult) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(response.body),
        status_code=_STATUS_BY_OUTCOME[response.outcome],
        headers=response.metadata,
    )
