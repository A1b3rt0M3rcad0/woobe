from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
    invoke_model_with_optional_streaming,
)
from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    handle_ask_stream,
)


def _disable_signal_handlers() -> None:
    return None


@asynccontextmanager
async def _serve_app(app: FastAPI) -> AsyncIterator[str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    sock.setblocking(False)
    host, port = sock.getsockname()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = _disable_signal_handlers
    task = asyncio.create_task(server.serve(sockets=[sock]))

    try:
        for _ in range(200):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError("Uvicorn exited before the test server started")
            await asyncio.sleep(0.01)
        else:
            raise TimeoutError("Timed out waiting for the local Uvicorn server")

        yield f"http://{host}:{port}"
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=3)
        finally:
            sock.close()


def _openai_chunk(content: str | None, *, finish_reason: str | None = None) -> str:
    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    payload = {
        "id": "chatcmpl-stream-boundary",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


async def _next_runtime_event(channel: RuntimeStreamChannel, event_type: str):
    while True:
        event = await asyncio.wait_for(channel.queue.get(), timeout=2)
        if event.event_type == event_type:
            return event


@pytest.mark.asyncio
async def test_real_chatopenai_adapter_emits_first_token_before_upstream_completion() -> None:
    upstream = FastAPI()
    first_chunk_sent = asyncio.Event()
    release_upstream = asyncio.Event()
    upstream_completed = asyncio.Event()

    @upstream.post("/v1/chat/completions")
    async def fake_chat_completions(request: Request) -> StreamingResponse:
        body = await request.json()
        assert body["stream"] is True

        async def generate() -> AsyncIterator[str]:
            yield _openai_chunk("Era")
            first_chunk_sent.set()
            await release_upstream.wait()
            yield _openai_chunk(" uma vez")
            yield _openai_chunk(None, finish_reason="stop")
            yield "data: [DONE]\n\n"
            upstream_completed.set()

        return StreamingResponse(generate(), media_type="text/event-stream")

    async with _serve_app(upstream) as upstream_url:
        model = ChatOpenAI(
            api_key="test-key",
            base_url=f"{upstream_url}/v1",
            model="test-model",
            streaming=True,
            stream_usage=False,
            timeout=5,
        )
        channel = RuntimeStreamChannel()
        context_token = current_runtime_stream.set(channel)
        task: asyncio.Task[Any] | None = None

        try:
            task = asyncio.create_task(
                invoke_model_with_optional_streaming(
                    model=model,
                    messages=[HumanMessage(content="Me conte uma história grande")],
                    phase="final_response_generation",
                    provider="fake-openai",
                    model_name="test-model",
                )
            )

            await asyncio.wait_for(first_chunk_sent.wait(), timeout=2)
            first_token = await _next_runtime_event(channel, "token")

            assert first_token.payload["content"] == "Era"
            assert task.done() is False
            assert upstream_completed.is_set() is False
            assert channel.public_output == "Era"

            release_upstream.set()
            result = await asyncio.wait_for(task, timeout=3)

            assert result.content == "Era uma vez"
            assert upstream_completed.is_set() is True
            assert channel.public_output == "Era uma vez"
        finally:
            release_upstream.set()
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            current_runtime_stream.reset(context_token)


def _sse(event_type: str, **payload: Any) -> str:
    body = {
        "protocol_version": 1,
        "type": event_type,
        **payload,
    }
    return f"event: {event_type}\ndata: {json.dumps(body)}\n\n"


class _ControlledHttpStreamService:
    def __init__(self) -> None:
        self.first_token_emitted = asyncio.Event()
        self.release = asyncio.Event()
        self.completed = asyncio.Event()

    async def stream(self, input_dto, _is_disconnected=None):
        del input_dto
        run_id = "run-tcp-boundary"
        yield _sse("meta", run_id=run_id)
        yield _sse(
            "token",
            run_id=run_id,
            content="Era",
            visibility="assistant",
            channel="final",
            phase="final_response_generation",
        )
        self.first_token_emitted.set()
        await self.release.wait()
        yield _sse(
            "token",
            run_id=run_id,
            content=" uma vez",
            visibility="assistant",
            channel="final",
            phase="final_response_generation",
        )
        yield _sse("done", run_id=run_id, answer="Era uma vez")
        self.completed.set()


async def _allow_environment(*_args) -> None:
    return None


async def _read_sse_event(lines, expected_type: str) -> dict[str, Any]:
    while True:
        event_type: str | None = None
        data_lines: list[str] = []

        while True:
            line = await anext(lines)
            if line == "":
                break
            if line.startswith("event:"):
                event_type = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())

        if event_type != expected_type:
            continue
        payload = json.loads("\n".join(data_lines))
        assert isinstance(payload, dict)
        return payload


@pytest.mark.asyncio
async def test_real_uvicorn_tcp_stream_delivers_first_sse_before_service_completion() -> None:
    service = _ControlledHttpStreamService()
    app = FastAPI()

    @app.post("/stream")
    async def stream(request: Request) -> StreamingResponse:
        return await handle_ask_stream(request, service, _allow_environment)

    try:
        async with _serve_app(app) as base_url:
            timeout = httpx.Timeout(5.0, connect=2.0, read=5.0, write=2.0, pool=2.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/stream",
                    json={
                        "project_id": "00000000-0000-0000-0000-000000000001",
                        "agent_id": "00000000-0000-0000-0000-000000000002",
                        "message": "Me conte uma história grande",
                        "execution_context": "playground",
                    },
                ) as response:
                    assert response.status_code == 200
                    assert response.headers["content-type"].startswith("text/event-stream")
                    assert response.headers["cache-control"] == "no-cache, no-transform"
                    assert response.headers["x-accel-buffering"] == "no"

                    await asyncio.wait_for(service.first_token_emitted.wait(), timeout=2)
                    lines = response.aiter_lines()
                    first_token = await asyncio.wait_for(
                        _read_sse_event(lines, "token"),
                        timeout=2,
                    )

                    assert first_token["content"] == "Era"
                    assert service.completed.is_set() is False

                    service.release.set()
                    second_token = await asyncio.wait_for(
                        _read_sse_event(lines, "token"),
                        timeout=2,
                    )
                    terminal = await asyncio.wait_for(
                        _read_sse_event(lines, "done"),
                        timeout=2,
                    )

                    assert second_token["content"] == " uma vez"
                    assert terminal["answer"] == "Era uma vez"
                    assert service.completed.is_set() is True
    finally:
        service.release.set()

