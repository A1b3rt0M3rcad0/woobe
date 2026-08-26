from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.presentation import public_runtime
from shared.security.http_guard import (
    is_runtime_execution_request,
    is_runtime_path,
    public_runtime_interface,
)


def test_public_runtime_reattach_uses_stream_interface() -> None:
    assert public_runtime_interface(
        "GET",
        "/v1/runs/00000000-0000-0000-0000-000000000001/stream",
    ) == "stream"
    assert public_runtime_interface(
        "GET",
        "/v1/sessions/00000000-0000-0000-0000-000000000001/active-run",
    ) == "stream"
    assert (
        is_runtime_path(
            "/v1/runs/00000000-0000-0000-0000-000000000001/stream"
        )
        is True
    )
    assert (
        is_runtime_path(
            "/v1/sessions/00000000-0000-0000-0000-000000000001/active-run"
        )
        is True
    )


def test_public_runtime_reattach_does_not_consume_execution_concurrency() -> None:
    assert is_runtime_execution_request(
        "GET", "/v1/runs/00000000-0000-0000-0000-000000000001/stream"
    ) is False
    assert is_runtime_execution_request(
        "GET", "/v1/sessions/00000000-0000-0000-0000-000000000001/active-run"
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
