from __future__ import annotations

import asyncio
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

    async def cancel(actual_target_type, actual_run_id, _request):
        calls.append((actual_target_type, actual_run_id))
        return {
            "success": True,
            "data": {
                "run_id": str(actual_run_id),
                "status": "cancel_requested",
            },
        }

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "cancel", cancel)

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
async def test_public_cancel_route_allows_idempotent_retry_over_asgi_boundary(
    monkeypatch,
    target_type: str,
) -> None:
    run_id = uuid4()
    dispatches = 0

    async def cancel(actual_target_type, actual_run_id, _request):
        nonlocal dispatches
        assert actual_target_type == target_type
        assert actual_run_id == run_id
        dispatches += 1
        return {
            "success": True,
            "data": {
                "run_id": str(actual_run_id),
                "status": "cancel_requested",
            },
        }

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "cancel", cancel)

    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/v1/runs/{run_id}/cancel",
            headers={"x-runtime-target": target_type},
        )
        retry = await client.post(
            f"/v1/runs/{run_id}/cancel",
            headers={"x-runtime-target": target_type},
        )

    assert first.status_code == 202
    assert retry.status_code == 202
    assert first.json() == retry.json()
    assert dispatches == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_public_reattach_route_keeps_target_specific_sse_contract(
    monkeypatch,
    target_type: str,
) -> None:
    run_id = uuid4()
    calls: list[tuple[str, object]] = []

    async def reattach(actual_target_type, actual_run_id, _request):
        calls.append((actual_target_type, actual_run_id))

        async def generate():
            yield 'event: run.state\ndata: {"status":"cancelled","output":"partial"}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "reattach", reattach)

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


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_public_observer_remains_attached_while_second_client_cancels(
    monkeypatch,
    target_type: str,
) -> None:
    run_id = uuid4()
    observer_started = asyncio.Event()
    cancel_requested = asyncio.Event()

    async def reattach(actual_target_type, actual_run_id, _request):
        assert actual_target_type == target_type
        assert actual_run_id == run_id

        async def generate():
            observer_started.set()
            yield 'event: run.state\ndata: {"status":"running","output":"partial"}\n\n'
            await cancel_requested.wait()
            yield 'event: cancelled\ndata: {"status":"cancelled","output":"partial"}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    async def cancel(actual_target_type, actual_run_id, _request):
        assert actual_target_type == target_type
        assert actual_run_id == run_id
        cancel_requested.set()
        return {
            "success": True,
            "data": {
                "run_id": str(actual_run_id),
                "status": "cancel_requested",
            },
        }

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "reattach", reattach)
    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "cancel", cancel)

    app = _app()
    observer_transport = ASGITransport(app=app)
    control_transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=observer_transport, base_url="http://observer") as observer,
        AsyncClient(transport=control_transport, base_url="http://control") as control,
    ):
        observer_task = asyncio.create_task(
            observer.get(
                f"/v1/runs/{run_id}/stream",
                headers={"x-runtime-target": target_type},
            )
        )
        await asyncio.wait_for(observer_started.wait(), timeout=1)
        assert not observer_task.done()

        cancel_response = await control.post(
            f"/v1/runs/{run_id}/cancel",
            headers={"x-runtime-target": target_type},
        )
        observer_response = await asyncio.wait_for(observer_task, timeout=1)

    assert cancel_response.status_code == 202
    assert observer_response.status_code == 200
    assert '"status":"running"' in observer_response.text
    assert 'event: cancelled' in observer_response.text
    assert '"status":"cancelled"' in observer_response.text
