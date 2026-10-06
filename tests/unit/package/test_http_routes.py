from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from woobe_api.http.package.routes import router
from woobe_api.middleware.package_limits import PackageBodyLimitsMiddleware
from woobe_api.security.operation_catalog import resolve_operation


@pytest.mark.asyncio
async def test_package_status_exposes_accepted_as_incomplete_and_uses_read_authority(
    monkeypatch,
):
    project, operation = uuid4(), uuid4()
    service = SimpleNamespace(
        status=AsyncMock(
            return_value={
                "package_schema_version": "1.0",
                "operation_id": str(operation),
                "state": "accepted",
                "terminal": False,
            }
        )
    )
    monkeypatch.setattr(
        "woobe_api.http.package.routes.build_package_service", lambda: service
    )
    app = FastAPI()

    @app.middleware("http")
    async def actor(request, call_next):
        request.state.principal = "authenticated-test-actor"
        return await call_next(request)

    app.include_router(router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://woobe.test"
    ) as client:
        result = await client.get(
            f"/projects/{project}/packages/operations/{operation}"
        )
    assert result.status_code == 200
    assert result.json()["meta"]["complete"] is False
    service.status.assert_awaited_once_with(
        project_id=project, principal="authenticated-test-actor", operation_id=operation
    )
    assert (
        resolve_operation(
            "GET", f"/projects/{project}/packages/operations/{operation}"
        )[0]
        == "project:read"
    )
    assert (
        resolve_operation("POST", f"/projects/{project}/packages/operations/lookup")[0]
        == "project:read"
    )


@pytest.mark.asyncio
async def test_invalid_package_plan_cannot_echo_input_values(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://woobe.test"
    ) as client:
        result = await client.post(
            f"/projects/{uuid4()}/packages/plan",
            json={"unknown": "protected-do-not-echo"},
        )
    assert result.status_code == 422
    assert "protected-do-not-echo" not in result.text


@pytest.mark.asyncio
async def test_chunked_package_body_cannot_bypass_limit_with_a_small_content_length():
    received = []

    async def endpoint(scope, receive, send):
        total = 0
        while True:
            message = await receive()
            total += len(message.get("body", b""))
            if not message.get("more_body", False):
                break
        received.append(total)
        await JSONResponse({"size": total})(scope, receive, send)

    async def chunks():
        for _ in range(5):
            yield b"x" * (512 << 10)

    app = PackageBodyLimitsMiddleware(endpoint)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://woobe.test"
    ) as client:
        result = await client.post(
            f"/projects/{uuid4()}/packages/plan",
            content=chunks(),
            headers={"Content-Length": "1"},
        )
    assert result.status_code == 413
    assert received == []
