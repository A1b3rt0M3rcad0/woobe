import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from modules.agent.application.execution_strategy_registry import (
    list_execution_strategies,
)
from woobe_api.http.agent.execution_strategy_routes import router


@pytest.mark.asyncio
async def test_execution_strategy_catalog_uses_api_envelope_and_backend_metadata() -> None:
    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ai/execution-strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "ok"
    assert payload["data"] == list_execution_strategies()
    standard = payload["data"][0]
    assert standard["compatibility"]["operations"] == ["language.generate"]
    assert standard["compatibility"]["requires_conversation"] is True
    assert standard["compatibility"]["context_mode"] == "required"

