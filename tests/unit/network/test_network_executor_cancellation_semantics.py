from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    NetworkExecutionCancelled,
    NetworkExecutor,
)


class _Store:
    def __init__(self) -> None:
        self.invocation_id = uuid4()
        self.fail_calls: list[tuple] = []
        self.events: list[str] = []

    async def is_cancel_requested(self, _execution_id):
        return False

    async def start_invocation(self, **_kwargs):
        return SimpleNamespace(
            id=self.invocation_id,
            agent_session_id=None,
            context_state="stateless",
            previous_invocation_count=0,
        )

    async def complete_invocation(self, *_args, **_kwargs):
        raise AssertionError("cancelled invocation must not complete")

    async def fail_invocation(self, *args, **kwargs):
        self.fail_calls.append((args, kwargs))

    async def emit(self, _execution_id, event_type, _payload, *, invocation_id=None):
        self.events.append(event_type)


class _CancellingInvoker:
    async def invoke(self, **_kwargs):
        raise NetworkExecutionCancelled("Network execution was cancelled")


@pytest.mark.asyncio
async def test_executor_propagates_cancellation_without_marking_agent_run_failed() -> None:
    node_id = uuid4()
    agent_id = uuid4()
    execution = SimpleNamespace(
        id=uuid4(),
        network_id=uuid4(),
        project_id=uuid4(),
        network_session_id=uuid4(),
        network_version_id=uuid4(),
        input_message="cancel this run",
        draft_revision=None,
    )
    version = SimpleNamespace(
        kind="release",
        definition={
            "schema_version": 2,
            "root_node_id": str(node_id),
            "nodes": [
                {
                    "id": str(node_id),
                    "agent_id": str(agent_id),
                    "label": "Root",
                    "capability_description": "Coordinates the response.",
                    "position": {"x": 0, "y": 0},
                    "binding": {"source": "release", "release_id": str(uuid4())},
                }
            ],
            "edges": [],
            "settings": {
                "session_mode": "stateless",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 30,
            },
        },
        resolved_bindings={
            str(node_id): {
                "release_id": str(uuid4()),
                "session_mode": "stateless",
            }
        },
    )
    store = _Store()

    with pytest.raises(NetworkExecutionCancelled):
        await NetworkExecutor(invoker=_CancellingInvoker(), store=store).execute(
            execution,
            version,
        )

    assert store.fail_calls == []
    assert "agent_invocation_started" in store.events
    assert "agent_invocation_failed" not in store.events
