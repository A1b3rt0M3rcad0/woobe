import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from woobe_api.http.agent.context_assembler_routes import router


@pytest.mark.asyncio
async def test_context_assembler_catalog_uses_api_envelope_and_backend_metadata() -> None:
    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ai/context-assemblers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "ok"
    assert payload["data"] == [
        {
            "name": "default",
            "version": "v1",
            "display_name": "Default Context",
            "description": (
                "Deterministic context assembly using Context Policy v1 budgets, "
                "source priorities and pressure handling."
            ),
            "behavior": (
                "Preserves mandatory system and user input, selects session and runtime "
                "context within configured budgets, applies pressure trimming, ordering "
                "and deduplication, and records provenance in a Context Snapshot for every "
                "Model Invocation."
            ),
            "is_default": True,
        }
    ]
