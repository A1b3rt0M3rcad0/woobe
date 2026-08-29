from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient

import public_runtime_routes
from shared.security.principal import ProjectApiPrincipal


def _principal(target_type: str) -> ProjectApiPrincipal:
    target_id = uuid4()
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="rai_live_http_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        target_type=target_type,
        target_id=target_id,
        agent_id=target_id if target_type == "agent" else None,
        environment="production",
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=datetime.now(UTC),
    )


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(public_runtime_routes.router)

    @app.middleware("http")
    async def bind_runtime_principal(request: Request, call_next):
        target_type = request.headers.get("x-runtime-target", "agent")
        request.state.principal = _principal(target_type)
        return await call_next(request)

    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_public_cancel_route_dispatches_over_real_asgi_boundary(
    monkeypatch,
    target_type: str,
) -> None:
    run_id = uuid4()
    calls: list[tuple[str, object]] = []

    async def cancel_agent(actual_run_id, _request):
        calls.append(("agent", actual_run_id))
        return {"success": True, "data": {"run_id": str(actual_run_id), "status": "cancel_requested"}}

    async def cancel_network(actual_run_id, _request):
        calls.append(("network", actual_run_id))
        return {"success": True, "data": {"run_id": str(actual_run_id), "status": "cancel_requested"}}

    monkeypatch.setattr(public_runtime_routes, "cancel_agent_run", cancel_agent)
    monkeypatch.setattr(public_runtime_routes, "cancel_network_run", cancel_network)

    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/v1/runs/{run_id}/cancel",
            headers={"x-runtime-target": target_type},
        )

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "cancel_requested"
    assert calls == [(target_type, run_id)]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_public_reattach_route_keeps_target_specific_sse_contract(
    monkeypatch,
    target_type: str,
) -> None:
    run_id = uuid4()
    calls: list[tuple[str, object]] = []

    async def attach_agent(actual_run_id, _request):
        calls.append(("agent", actual_run_id))

        async def generate():
            yield 'event: run.state\ndata: {"status":"cancelled","output":"partial"}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    async def attach_network(actual_run_id, _request):
        calls.append(("network", actual_run_id))

        async def generate():
            yield 'event: run.state\ndata: {"status":"cancelled","output":"partial"}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    monkeypatch.setattr(public_runtime_routes, "attach_agent_run", attach_agent)
    monkeypatch.setattr(public_runtime_routes, "reattach_network_execution", attach_network)

    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/runs/{run_id}/stream",
            headers={"x-runtime-target": target_type},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert '"status":"cancelled"' in response.text
    assert calls == [(target_type, run_id)]
