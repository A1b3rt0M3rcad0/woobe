import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import Request

from shared.infra.errors import RuntimeTimeoutError
from shared.security.http_guard import is_runtime_execution_request
from shared.security.principal import ProjectApiPrincipal


async def _security_body(request: Request) -> Any:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            return {
                key: value
                for key, value in form.items()
                if isinstance(value, (str, int, float, bool))
            }
        except Exception:
            return None
    try:
        return await request.json()
    except Exception:
        return None


async def enforce_request_security(request: Request) -> AsyncIterator[None]:
    body = await _security_body(request)

    guard = request.app.state.security_guard
    principal = await guard.authenticate_and_authorize(
        request,
        body=body,
        query_params=dict(request.query_params),
        path_params=dict(request.path_params),
    )
    request.state.principal = principal

    lease_id: UUID | None = None
    if guard.requires_runtime_permit(request, principal):
        if not isinstance(principal, ProjectApiPrincipal):
            raise RuntimeError("Runtime permit requires a project API principal")
        lease_id = await guard.acquire_runtime_permit(principal)

    try:
        if is_runtime_execution_request(request.method, request.url.path):
            try:
                async with asyncio.timeout(guard.runtime_timeout_seconds):
                    yield
            except TimeoutError as exc:
                raise RuntimeTimeoutError("Runtime request timed out") from exc
        else:
            yield
    finally:
        if lease_id is not None:
            await guard.release_runtime_permit(lease_id)
