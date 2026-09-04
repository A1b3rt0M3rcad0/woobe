from types import SimpleNamespace
from uuid import uuid4

import pytest

from woobe_api.http.network import public_runtime
from woobe_api.security.http_guard import (
    is_runtime_execution_request,
    is_runtime_path,
    public_runtime_interface,
)


RUN_ID = "00000000-0000-0000-0000-000000000001"


def test_public_runtime_reattach_uses_stream_interface() -> None:
    assert public_runtime_interface(
        "GET",
        f"/v1/runs/{RUN_ID}/stream",
    ) == "stream"
    assert public_runtime_interface(
        "GET",
        f"/v1/sessions/{RUN_ID}/active-run",
    ) == "stream"
    assert is_runtime_path(f"/v1/runs/{RUN_ID}/stream") is True
    assert is_runtime_path(f"/v1/sessions/{RUN_ID}/active-run") is True


def test_public_runtime_run_cancel_is_control_not_new_execution() -> None:
    path = f"/v1/runs/{RUN_ID}/cancel"
    assert public_runtime_interface("POST", path) == "http"
    assert is_runtime_path(path) is True
    assert is_runtime_execution_request("POST", path) is False


def test_public_runtime_reattach_does_not_consume_execution_concurrency() -> None:
    assert is_runtime_execution_request(
        "GET", f"/v1/runs/{RUN_ID}/stream"
    ) is False
    assert is_runtime_execution_request(
        "GET", f"/v1/sessions/{RUN_ID}/active-run"
    ) is False


@pytest.mark.asyncio
async def test_public_network_stream_uses_same_canonical_reattach_path(monkeypatch) -> None:
    execution_id = uuid4()
    execution = SimpleNamespace(id=execution_id)
    sentinel = object()

    async def submit(request):
        return SimpleNamespace(), SimpleNamespace(), execution

    async def reattach(value, request):
        assert value == execution_id
        return sentinel

    monkeypatch.setattr(public_runtime, "_submit", submit)
    monkeypatch.setattr(public_runtime, "reattach_network_execution", reattach)

    result = await public_runtime.stream_network_http(SimpleNamespace())
    assert result is sentinel
