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
    operation_metadata = dict(metadata or {})
    route = getattr(fastapi_request, "scope", {}).get("route")
    operation_name = getattr(route, "name", None)
    if route is not None:
        from woobe_api.security.operation_catalog import resolve_operation, verified_query_context
        from woobe_api.security.http_guard import HttpSecurityGuard

        permission, _ = resolve_operation(
            fastapi_request.method, fastapi_request.url.path, body
        )
        if permission is not None:
            operation_metadata["required_permission"] = permission
            operation_metadata["authorization_path_params"] = verified_query_context(
                fastapi_request.method, fastapi_request.url.path,
                HttpSecurityGuard._authorization_path_params(
                    fastapi_request, dict(fastapi_request.path_params)
                ),
                dict(fastapi_request.query_params),
            )
    if operation_name in {
        "create_project",
        "create_agent",
        "create_api_key",
        "create_runtime_api_key",
        "rotate_api_key",
    } and fastapi_request.headers.get("idempotency-key"):
        operation_metadata.update(
            idempotency_key=fastapi_request.headers["idempotency-key"],
            operation_name=operation_name,
        )
    if "agent_id" in fastapi_request.path_params and fastapi_request.method in {"POST", "PATCH", "PUT", "DELETE"} and fastapi_request.headers.get("if-match"):
        operation_metadata["expected_agent_revision"] = fastapi_request.headers["if-match"]
    operation_request = OperationRequest(
        principal=principal,
        body=body,
        query_params=dict(fastapi_request.query_params),
        path_params=dict(fastapi_request.path_params),
        metadata=operation_metadata,
    )

    response = await handler(operation_request)
    return response


def response_adapter(response: OperationResult) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(response.body),
        status_code=_STATUS_BY_OUTCOME[response.outcome],
        headers=response.metadata,
    )
