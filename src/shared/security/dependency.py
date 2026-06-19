import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request

from shared.infra.errors import RuntimeTimeoutError
from shared.security.principal import ProjectApiPrincipal


def _is_runtime_path(path: str) -> bool:
    return path.startswith("/runtime/") or path.startswith("/agent/runtime/")


async def enforce_request_security(request: Request) -> AsyncIterator[None]:
    body: Any = None
    try:
        body = await request.json()
    except Exception:
        body = None

    guard = request.app.state.security_guard
    principal = await guard.authenticate_and_authorize(
        request,
        body=body,
        query_params=dict(request.query_params),
        path_params=dict(request.path_params),
    )
    request.state.principal = principal

    acquired = False
    if guard.requires_runtime_permit(request, principal):
        if not isinstance(principal, ProjectApiPrincipal):
            raise RuntimeError("Runtime permit requires a project API principal")
        await guard.acquire_runtime_permit(principal)
        acquired = True

    try:
        if _is_runtime_path(request.url.path):
            try:
                async with asyncio.timeout(guard.runtime_timeout_seconds):
                    yield
            except TimeoutError as exc:
                raise RuntimeTimeoutError("Runtime request timed out") from exc
        else:
            yield
    finally:
        if acquired and isinstance(principal, ProjectApiPrincipal):
            await guard.release_runtime_permit(principal)
