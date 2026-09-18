import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from woobe_api.http.agent.context_assembler_routes import router


@pytest.mark.asyncio
async def test_context_assembler_catalog_uses_stable_unversioned_identity() -> None:
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
    assert len(payload["data"]) == 1

    standard = payload["data"][0]
    assert standard["name"] == "standard"
    assert standard["display_name"] == "Standard Context Manager"
    assert standard["supports_skills"] is True
    assert standard["is_default"] is True
    assert "version" not in standard
    assert "strategy_name" not in standard
    assert "strategy_version" not in standard
    assert "is_system_default_alias" not in standard
