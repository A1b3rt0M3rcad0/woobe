"""Calibrate the fault harness; real commit proof belongs to live integration."""

import json

import httpx
import pytest

from tests.integration.cli import retest_operational


@pytest.mark.asyncio
async def test_fault_proxy_forwards_bytes_and_loses_only_the_accepted_response(
    monkeypatch,
):
    original_client = httpx.AsyncClient
    operation = "12345678-1234-4321-8321-123456789012"
    requests = []

    async def upstream(request):
        requests.append((request.method, request.url.path))
        if request.method == "POST":
            assert json.loads(request.content) == {"operation_id": operation}
        return httpx.Response(
            200, json={"success": True, "data": {"operation_id": operation}}
        )

    def client(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(upstream))

    monkeypatch.setattr(retest_operational.httpx, "AsyncClient", client)
    async with retest_operational.lose_committed_response(
        "http://upstream.test", "/deployments"
    ) as (origin, accepted):
        async with original_client(trust_env=False, timeout=5) as downstream:
            with pytest.raises(httpx.RemoteProtocolError):
                await downstream.post(
                    origin + "/deployments", json={"operation_id": operation}
                )
            assert accepted == [{"operation_id": operation}]
            recovered = await downstream.get(origin + "/operations/" + operation)
            assert recovered.json()["data"] == accepted[0]
            assert len(accepted) == 1
    assert requests == [("POST", "/deployments"), ("GET", "/operations/" + operation)]
