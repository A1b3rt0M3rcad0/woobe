from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
import pytest_asyncio

from tests.fakes.openai_provider import app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fake-provider"
    ) as value:
        yield value


@pytest.mark.asyncio
async def test_health_and_non_stream_completion_are_deterministic(
    client: httpx.AsyncClient,
) -> None:
    health = await client.get("/health")
    assert health.json() == {"status": "ok"}

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "fake-success",
            "messages": [{"role": "user", "content": "release"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "Woobe release gate passed"
    assert payload["usage"] == {
        "prompt_tokens": 7,
        "completion_tokens": 5,
        "total_tokens": 12,
    }


@pytest.mark.asyncio
async def test_stream_completion_has_tokens_terminal_chunk_usage_and_done(
    client: httpx.AsyncClient,
) -> None:
    async with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": "fake-stream", "stream": True, "messages": []},
    ) as response:
        lines = [
            line async for line in response.aiter_lines() if line.startswith("data: ")
        ]

    assert response.status_code == 200
    assert lines[-1] == "data: [DONE]"
    chunks = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    contents = [
        choice["delta"]["content"]
        for chunk in chunks
        for choice in chunk["choices"]
        if "content" in choice["delta"]
    ]
    assert "".join(contents) == "Woobe release gate passed"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert chunks[-1]["usage"]["total_tokens"] == 12


@pytest.mark.asyncio
async def test_tool_call_contract_is_available_in_sync_and_stream_modes(
    client: httpx.AsyncClient,
) -> None:
    sync_response = await client.post(
        "/v1/chat/completions",
        headers={"x-fake-scenario": "tool"},
        json={"model": "fake-tool", "messages": [], "tools": [{"type": "function"}]},
    )
    tool = sync_response.json()["choices"][0]["message"]["tool_calls"][0]
    assert tool["function"]["name"] == "release_gate"

    async with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"x-fake-scenario": "tool"},
        json={"model": "fake-tool", "stream": True, "messages": []},
    ) as response:
        body = await response.aread()
    assert b'"finish_reason":"tool_calls"' in body
    assert b'"name":"release_gate"' in body


@pytest.mark.asyncio
async def test_primary_failure_can_be_recovered_by_deterministic_fallback(
    client: httpx.AsyncClient,
) -> None:
    primary = await client.post(
        "/v1/chat/completions",
        json={"model": "fake-primary-fail", "messages": []},
    )
    assert primary.status_code == 503

    fallback = await client.post(
        "/v1/chat/completions",
        json={"model": "fake-fallback", "messages": []},
    )
    assert fallback.status_code == 200
    assert fallback.json()["choices"][0]["message"]["content"].endswith("passed")


@pytest.mark.asyncio
async def test_slow_and_cancellable_scenarios_are_bounded(
    client: httpx.AsyncClient,
) -> None:
    started = time.perf_counter()
    slow = await client.post(
        "/v1/chat/completions",
        headers={"x-fake-scenario": "timeout", "x-fake-delay-ms": "50"},
        json={"model": "fake-timeout", "messages": []},
    )
    elapsed = time.perf_counter() - started
    assert slow.status_code == 200
    assert 0.04 <= elapsed < 0.5

    async with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"x-fake-scenario": "cancel", "x-fake-delay-ms": "1"},
        json={"model": "fake-cancel", "stream": True, "messages": []},
    ) as response:
        iterator = response.aiter_lines()
        observed = []
        async for line in iterator:
            if line.startswith("data: "):
                observed.append(line)
            if len(observed) == 3:
                break
        await response.aclose()

    assert len(observed) == 3
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_embedding_batches_are_deterministic_with_native_dimensions(client):
    payload = {"model": "fake-embedding", "input": ["Knowledge A", "Knowledge B"]}
    first = await client.post("/v1/embeddings", json=payload)
    repeated = await client.post("/v1/embeddings", json=payload)
    assert first.status_code == 200
    assert first.json() == repeated.json()
    rows = first.json()["data"]
    assert [row["index"] for row in rows] == [0, 1]
    assert all(len(row["embedding"]) == 1536 for row in rows)
    assert rows[0]["embedding"] != rows[1]["embedding"]
    assert (await client.post("/v1/embeddings", json={"input": []})).status_code == 422
    assert (
        await client.post("/v1/embeddings", json={"input": "test", "dimensions": True})
    ).status_code == 422


@pytest.mark.asyncio
async def test_embedding_accepts_openai_client_token_arrays(client):
    payload = {"model": "fake-embedding", "input": [[12, 34, 56]], "dimensions": 1536}
    response = await client.post("/v1/embeddings", json=payload)
    assert response.status_code == 200
    assert len(response.json()["data"][0]["embedding"]) == 1536
    assert response.json()["usage"]["prompt_tokens"] == 3
    assert (
        await client.post("/v1/embeddings", json={"input": [[True]]})
    ).status_code == 422


@pytest.mark.asyncio
async def test_portable_stream_calls_advertised_tool_then_returns_structured_answer(
    client,
):
    payload = {
        "model": "fake-portable-http",
        "stream": True,
        "messages": [],
        "tools": [{"type": "function", "function": {"name": "guarded_lookup"}}],
        "response_format": {"type": "json_object"},
    }
    first = await client.post("/v1/chat/completions", json=payload)
    assert '"name":"guarded_lookup"' in first.text
    assert '"finish_reason":"tool_calls"' in first.text
    payload["messages"] = [{"role": "tool", "content": "portable-tenant"}]
    second = await client.post("/v1/chat/completions", json=payload)
    assert '"tool_calls"' not in second.text
    chunks = [
        json.loads(line[6:])
        for line in second.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    content = "".join(
        chunk["choices"][0]["delta"].get("content", "") for chunk in chunks
    )
    assert json.loads(content) == {"answer": "Woobe portable composition passed"}
