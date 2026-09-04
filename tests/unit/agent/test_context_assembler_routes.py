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
            "display_name": "Standard Context Manager",
            "description": (
                "Balanced deterministic context management for general-purpose Agent execution."
            ),
            "behavior": (
                "Builds each Model Invocation context deterministically from the Agent's available "
                "context sources, applying Context Policy v1 budgets, priorities, pressure handling, "
                "ordering, deduplication, and provenance capture."
            ),
            "recommended_for": [
                "General-purpose Agents that need predictable context behavior.",
                "Production workloads where replayability and stable snapshot behavior matter.",
            ],
            "capabilities": [
                "Preserves mandatory system instructions and the current user input.",
                "Balances session history, knowledge, tool, artifact, delegation, and runtime context within configured budgets.",
                "Applies pressure trimming, ordering, and deduplication before each Model Invocation.",
                "Records source contributions and provenance in the Context Snapshot.",
            ],
            "limitations": [
                "Does not perform autonomous context planning or iterative retrieval.",
                "Behavior is bounded by Context Policy v1 and the context sources available to the Agent.",
            ],
            "configuration": "Context Policy v1",
            "is_default": True,
        }
    ]
