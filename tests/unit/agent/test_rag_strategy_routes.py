import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from modules.agent.composition.factories.rag_runtime_factory import (
    build_rag_strategy_registry,
    list_rag_strategies,
)
from woobe_api.http.agent.rag_strategy_routes import router


def test_rag_strategy_catalog_is_derived_from_registered_runtime_strategies() -> None:
    registered = build_rag_strategy_registry().names()
    catalog = list_rag_strategies()

    assert tuple(item["name"] for item in catalog) == registered
    assert catalog == (
        {
            "name": "classic",
            "display_name": "Classic RAG",
            "description": (
                "Semantic retrieval using embeddings and vector search over the selected "
                "immutable Knowledge snapshot."
            ),
            "is_default": True,
            "config_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "config_schema_version": "1",
        },
    )


@pytest.mark.asyncio
async def test_rag_strategy_catalog_route_uses_api_envelope() -> None:
    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ai/rag-strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "ok"
    assert payload["data"] == [
        {
            "name": "classic",
            "display_name": "Classic RAG",
            "description": (
                "Semantic retrieval using embeddings and vector search over the selected "
                "immutable Knowledge snapshot."
            ),
            "is_default": True,
            "config_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "config_schema_version": "1",
        }
    ]
