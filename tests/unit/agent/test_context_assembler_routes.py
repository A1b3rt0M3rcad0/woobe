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

    descriptors = {
        (item["name"], item["version"]): item
        for item in payload["data"]
    }
    assert set(descriptors) == {
        ("default", "v3"),
        ("stdcm", "v1"),
        ("stdcm", "v2"),
        ("stdcm", "v3"),
    }

    system_default = descriptors[("default", "v3")]
    assert system_default["strategy_name"] == "stdcm"
    assert system_default["strategy_version"] == "v3"
    assert system_default["display_name"] == "Standard Context Manager v3"
    assert system_default["supports_skills"] is True
    assert system_default["is_default"] is True
    assert system_default["is_system_default_alias"] is True

    historical_v1 = descriptors[("stdcm", "v1")]
    assert historical_v1["strategy_version"] == "v1"
    assert historical_v1["display_name"] == "Standard Context Manager"
    assert historical_v1["supports_skills"] is False
    assert historical_v1["is_default"] is False

    programmable_v3 = descriptors[("stdcm", "v3")]
    assert programmable_v3["strategy_version"] == "v3"
    assert programmable_v3["supports_skills"] is True
    assert "compaction" in programmable_v3["behavior"].lower()
