from typing import Any

from fastapi import Request as FastAPIRequest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.security.principal import AuthenticatedPrincipal


async def request_adapter(fastapi_request: FastAPIRequest, handler: Any) -> Response:
    body: Any = None
    try:
        body = await fastapi_request.json()
    except Exception:
        body = None

    principal = getattr(fastapi_request.state, "principal", None)
    user = str(principal.user_id) if isinstance(principal, AuthenticatedPrincipal) else None
    http_request = Request(
        principal=principal,
        user=user,
        url=str(fastapi_request.url),
        method=fastapi_request.method,
        headers=dict(fastapi_request.headers),
        cookies=dict(fastapi_request.cookies),
        client_ip=fastapi_request.client.host if fastapi_request.client else None,
        body=body,
        query_params=dict(fastapi_request.query_params),
        path_params=dict(fastapi_request.path_params),
    )

    response = await handler(http_request)
    return response


def response_adapter(response: Response) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(response.body),
        status_code=response.status_code,
        headers=response.headers,
    )
