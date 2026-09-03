from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from modules.agent.infra.adapters import tool_executor as tool_executor_module
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.network.application.runtime import NetworkExecutionCancelled, NetworkExecutionSnapshot
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from woobe_workers.consumers.network.execution_worker import NetworkExecutionProcessor
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _BlockingHttpClient:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.interrupted = asyncio.Event()
        self.is_closed = False

    def build_request(self, **kwargs):
        return kwargs

    async def send(self, _request, **_kwargs):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.interrupted.set()
            raise


@pytest.mark.asyncio
async def test_network_cancel_interrupts_operational_http_tool_in_flight(monkeypatch) -> None:
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="call the external capability",
        draft_revision=None,
        definition_snapshot=None,
        resolved_bindings_snapshot=None,
        status="queued",
    )
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    await store.initialize(execution, ttl_seconds=3600)

    client = _BlockingHttpClient()
    http_executor = HttpToolExecutor(client=client)
    monkeypatch.setattr(
        tool_executor_module,
        "_validated_public_addresses",
        lambda _url: frozenset({"203.0.113.10"}),
    )

    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store
    task = asyncio.create_task(
        processor._execute_with_cancellation(
            execution.id,
            http_executor.execute(
                "GET",
                "https://tool.example.test/resource",
                timeout_ms=30_000,
            ),
        )
    )

    await asyncio.wait_for(client.started.wait(), timeout=1)
    await store.request_cancel(execution.id)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert client.interrupted.is_set()
