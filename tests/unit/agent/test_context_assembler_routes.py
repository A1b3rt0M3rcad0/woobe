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
                "Balanced deterministic context assembly for general-purpose Agent execution."
            ),
            "behavior": (
                "Preserves mandatory inputs, applies Context Policy v1 budgets and priorities, "
                "trims context under pressure, and records provenance in the Context Snapshot."
            ),
            "is_default": True,
        }
    ]
