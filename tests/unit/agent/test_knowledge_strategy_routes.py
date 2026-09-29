import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from modules.agent.application.knowledge_strategy_registry import (
    build_knowledge_strategy_registry,
    list_knowledge_strategies,
)
from woobe_api.http.agent.knowledge_strategy_routes import router


def test_knowledge_strategy_catalog_matches_registered_runtime_strategies() -> None:
    registry = build_knowledge_strategy_registry()
    catalog = list_knowledge_strategies()

    assert tuple(item["name"] for item in catalog) == tuple(
        descriptor.name for descriptor in registry.list_descriptors()
    )
    assert catalog[0]["name"] == "rag"
    assert catalog[0]["is_default"] is True


@pytest.mark.asyncio
async def test_knowledge_strategy_catalog_route_uses_api_envelope() -> None:
    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ai/knowledge-strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "ok"
    assert payload["data"][0]["name"] == "rag"
    assert payload["data"][0]["is_default"] is True
