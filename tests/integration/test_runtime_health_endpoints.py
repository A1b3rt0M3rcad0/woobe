from __future__ import annotations

from contextlib import AbstractAsyncContextManager

import pytest
from httpx import ASGITransport, AsyncClient


class FakeConnection:
    async def execute(self, statement):
        return statement


class ConnectionContext(AbstractAsyncContextManager):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def __aenter__(self):
        if self.fail:
            raise RuntimeError("database unavailable")
        return FakeConnection()

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def connect(self):
        return ConnectionContext(fail=self.fail)


@pytest.mark.asyncio
async def test_live_and_ready_when_database_is_available(app) -> None:
    app.state.async_engine = FakeEngine()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        live = await client.get("/live")
        ready = await client.get("/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "dependency": "database"}


@pytest.mark.asyncio
async def test_ready_returns_503_when_database_is_unavailable(app) -> None:
    app.state.async_engine = FakeEngine(fail=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "dependency": "database"}


@pytest.mark.asyncio
async def test_request_identifiers_are_returned(app) -> None:
    app.state.async_engine = FakeEngine()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/live",
            headers={"X-Request-ID": "request-123", "X-Correlation-ID": "correlation-456"},
        )

    assert response.headers["X-Request-ID"] == "request-123"
    assert response.headers["X-Correlation-ID"] == "correlation-456"
