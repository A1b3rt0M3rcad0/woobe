from typing import Any

from fastapi import Request as FastAPIRequest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


async def request_adapter(fastapi_request: FastAPIRequest, handler: Any) -> Response:
    body: Any = None
    try:
        body = await fastapi_request.json()
    except Exception:
        body = None

    http_request = Request(
        url=str(fastapi_request.url),
        method=fastapi_request.method,
        headers=dict(fastapi_request.headers),
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
