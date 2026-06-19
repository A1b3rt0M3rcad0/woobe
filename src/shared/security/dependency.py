from typing import Any

from fastapi import Request


async def enforce_request_security(request: Request) -> None:
    body: Any = None
    try:
        body = await request.json()
    except Exception:
        body = None

    principal = await request.app.state.security_guard.authenticate_and_authorize(
        request,
        body=body,
        query_params=dict(request.query_params),
        path_params=dict(request.path_params),
    )
    request.state.principal = principal
