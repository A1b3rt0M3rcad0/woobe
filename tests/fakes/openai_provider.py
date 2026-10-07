from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from tests.fakes.mcp_provider import app as mcp_peer

app = FastAPI(title="Woobe deterministic fake provider", version="1.0")
app.mount("/mcp-peer", mcp_peer)

_DEFAULT_TOKENS = ("Woo", "be", " release", " gate", " passed")


def _scenario(payload: dict[str, Any], header: str | None) -> str:
    if header:
        return header
    model = str(payload.get("model", "fake-success"))
    if model.startswith("fake-"):
        return model.removeprefix("fake-")
    return "success"


def _completion(payload: dict[str, Any], *, scenario: str) -> dict[str, Any]:
    completion_id = f"chatcmpl-{uuid4().hex}"
    message: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(_DEFAULT_TOKENS),
    }
    finish_reason = "stop"
    if payload.get("response_format"):
        message["content"] = json.dumps({"answer": "Woobe portable composition passed"})
    observed_tool = any(
        item.get("role") == "tool" or "portable-tenant" in str(item.get("content", ""))
        for item in payload.get("messages", [])
    )
    if (
        scenario in {"portable-tool", "portable-http"}
        and payload.get("tools")
        and payload.get("tool_choice") != "none"
        and not observed_tool
    ):
        available = [
            tool["function"]["name"]
            for tool in payload["tools"]
            if "lookup" in tool["function"]["name"].lower()
        ]
        if scenario == "portable-http":
            available = [name for name in available if "guarded" in name]
        if available:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_portable_" + uuid4().hex,
                        "type": "function",
                        "function": {"name": available[0], "arguments": "{}"},
                    }
                ],
            }
            finish_reason = "tool_calls"
    if scenario == "tool":
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_release_gate",
                    "type": "function",
                    "function": {
                        "name": "release_gate",
                        "arguments": json.dumps({"project_id": "project-a"}),
                    },
                }
            ],
        }
        finish_reason = "tool_calls"
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.get("model", "fake-success"),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 7,
            "completion_tokens": 5,
            "total_tokens": 12,
        },
    }


def _sse(data: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


async def _stream(
    request: Request,
    payload: dict[str, Any],
    *,
    scenario: str,
    delay_seconds: float,
) -> AsyncIterator[bytes]:
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time.time())
    model = payload.get("model", "fake-stream")

    yield _sse(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
    )

    if scenario == "tool":
        yield _sse(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_release_gate",
                                    "type": "function",
                                    "function": {
                                        "name": "release_gate",
                                        "arguments": '{"project_id":"project-a"}',
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
        )
        finish_reason = "tool_calls"
    else:
        token_count = 100 if scenario == "cancel" else len(_DEFAULT_TOKENS)
        for index in range(token_count):
            if await request.is_disconnected():
                return
            token = _DEFAULT_TOKENS[index % len(_DEFAULT_TOKENS)]
            yield _sse(
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": token},
                            "finish_reason": None,
                        }
                    ],
                }
            )
            if delay_seconds:
                await asyncio.sleep(delay_seconds)
        finish_reason = "stop"

    yield _sse(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 5,
                "total_tokens": 12,
            },
        }
    )
    yield b"data: [DONE]\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_fake_scenario: str | None = Header(default=None),
    x_fake_delay_ms: int = Header(default=0, ge=0, le=2_000),
) -> Any:
    payload = await request.json()
    scenario = _scenario(payload, x_fake_scenario)
    delay_seconds = x_fake_delay_ms / 1_000

    if scenario in {"error", "primary-fail"}:
        raise HTTPException(status_code=503, detail="deterministic provider failure")
    if scenario == "timeout":
        await asyncio.sleep(delay_seconds or 0.2)
    if payload.get("stream"):
        return StreamingResponse(
            _stream(request, payload, scenario=scenario, delay_seconds=delay_seconds),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return _completion(payload, scenario=scenario)


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> dict[str, Any]:
    """Deterministic local vectors for real ingestion/build/runtime tests."""
    import hashlib
    import math

    payload = await request.json()
    values = payload.get("input")
    values = [values] if isinstance(values, str) else values
    dimensions = payload.get("dimensions", 1536)

    def valid_input(value):
        if isinstance(value, str):
            return len(value.encode("utf-8")) <= 1 << 20
        return (
            isinstance(value, list)
            and 1 <= len(value) <= 65536
            and all(type(token) is int and 0 <= token <= 2**32 - 1 for token in value)
        )

    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 256
        or any(not valid_input(value) for value in values)
        or type(dimensions) is not int
        or not 1 <= dimensions <= 4096
    ):
        raise HTTPException(status_code=422, detail="Invalid embedding input")
    data = []
    for index, value in enumerate(values):
        material = (
            value.encode("utf-8")
            if isinstance(value, str)
            else json.dumps(value, separators=(",", ":")).encode()
        )
        digest = hashlib.sha256(material).digest()
        vector = [
            (digest[position % len(digest)] - 127.5) / 127.5
            for position in range(dimensions)
        ]
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        data.append(
            {
                "object": "embedding",
                "index": index,
                "embedding": [item / norm for item in vector],
            }
        )
    tokens = sum(
        max(1, len(value.split()) if isinstance(value, str) else len(value))
        for value in values
    )
    return {
        "object": "list",
        "model": payload.get("model", "fake-embedding"),
        "data": data,
        "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
    }
