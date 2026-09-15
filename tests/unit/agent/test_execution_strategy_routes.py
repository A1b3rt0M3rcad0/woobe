import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

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
    assert payload["data"] == [
        {
            "name": "standard",
            "display_name": "Standard",
            "description": (
                "General-purpose Woobe execution strategy for model and capability orchestration."
            ),
            "behavior": (
                "Invokes the configured model, executes bound capabilities when requested, "
                "feeds durable results back into the model, and continues until terminal output "
                "or runtime safety limits are reached."
            ),
            "recommended_for": [
                "General-purpose Agents that need predictable production behavior.",
                "Agents that use Tools, Knowledge, structured output, or multi-round capability calls.",
            ],
            "capabilities": [
                "Single-pass and multi-round Model execution.",
                "Parallel Tool calls within one capability round.",
                "Durable Tool-boundary recovery without replaying completed Tool side effects.",
                "Structured output validation and JSON repair.",
            ],
            "limitations": [
                "Does not add an explicit planning or reflection phase beyond model-directed capability use."
            ],
            "is_default": True,
        }
    ]
