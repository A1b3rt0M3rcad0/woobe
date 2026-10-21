from __future__ import annotations

import json

import httpx
import pytest

from woobe._transport.http import RuntimeTransport
from woobe.errors import WoobeProtocolError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("external_context", "expected_payload"),
    [
        (None, {"message": "Olá"}),
        ({}, {"message": "Olá", "external_context": {}}),
        (
            {"customer_id": "customer-123", "preferences": {"language": "pt-BR"}},
            {
                "message": "Olá",
                "external_context": {
                    "customer_id": "customer-123",
                    "preferences": {"language": "pt-BR"},
                },
            },
        ),
    ],
)
async def test_stream_new_run_serializes_external_context(
    external_context: dict | None,
    expected_payload: dict,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["idempotency_key"] = request.headers.get("Idempotency-Key")
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=b"",
        )

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        frames = [
            frame
            async for frame in transport.stream_new_run(
                key="runtime-key",
                message="Olá",
                session_id=None,
                external_context=external_context,
                idempotency_key="run-idempotency",
            )
        ]
    finally:
        await transport.aclose()

    assert frames == []
    assert captured["payload"] == expected_payload
    assert captured["idempotency_key"] == "run-idempotency"


@pytest.mark.asyncio
async def test_validate_contracts_calls_public_validator() -> None:
    captured: dict = {}

    output_contract = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }
    external_context = {
        "type": "object",
        "properties": {"age": {"type": "integer"}},
        "required": ["age"],
        "additionalProperties": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("Authorization")
        captured["accept"] = request.headers.get("Accept")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "valid": False,
                    "target_type": "agent",
                    "target_id": "agent-1",
                    "environment": "production",
                    "release_id": "release-1",
                    "release_version": "v2.0.0",
                    "output_contract": {
                        "valid": True,
                        "expected": output_contract,
                        "received": output_contract,
                        "expected_hash": "output",
                        "received_hash": "output",
                        "issues": [],
                    },
                    "external_context": {
                        "valid": False,
                        "expected": external_context,
                        "received": {
                            "type": "object",
                            "properties": {"age": {"type": "string"}},
                            "required": ["age"],
                            "additionalProperties": False,
                        },
                        "expected_hash": "expected",
                        "received_hash": "received",
                        "issues": [
                            {
                                "code": "FIELD_TYPE_MISMATCH",
                                "field": "age",
                                "expected": "integer",
                                "received": "string",
                            }
                        ],
                    },
                },
            },
        )

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        data = await transport.validate_contracts(
            key="runtime-key",
            output_contract=output_contract,
            external_context=external_context,
        )
    finally:
        await transport.aclose()

    assert captured == {
        "path": "/v1/contracts/validate",
        "authorization": "Bearer runtime-key",
        "accept": "application/json",
        "payload": {
            "output_contract": output_contract,
            "external_context": external_context,
        },
    }
    assert data["valid"] is False
    assert data["external_context"]["issues"][0]["code"] == "FIELD_TYPE_MISMATCH"


@pytest.mark.asyncio
async def test_validate_contracts_always_declares_both_contracts() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "valid": True,
                    "target_type": "agent",
                    "target_id": "agent-1",
                    "environment": "production",
                    "release_id": "release-1",
                    "release_version": "v1.0.0",
                    "output_contract": {
                        "valid": True,
                        "expected": None,
                        "received": None,
                        "expected_hash": "none",
                        "received_hash": "none",
                        "issues": [],
                    },
                    "external_context": {
                        "valid": True,
                        "expected": None,
                        "received": None,
                        "expected_hash": "none",
                        "received_hash": "none",
                        "issues": [],
                    },
                },
            },
        )

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        await transport.validate_contracts(
            key="runtime-key",
            output_contract=None,
            external_context=None,
        )
    finally:
        await transport.aclose()

    assert captured["payload"] == {
        "output_contract": None,
        "external_context": None,
    }


@pytest.mark.asyncio
async def test_validate_contracts_rejects_invalid_response_envelope() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(WoobeProtocolError, match="invalid envelope"):
            await transport.validate_contracts(
                key="runtime-key",
                output_contract=None,
                external_context=None,
            )
    finally:
        await transport.aclose()
