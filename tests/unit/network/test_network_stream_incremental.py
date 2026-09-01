from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import AgentInvocationResult, NetworkExecutor


class _EventStore:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def is_cancel_requested(self, execution_id):
        return False

    async def resolve_agent_session_mode(self, **kwargs):
        return kwargs.get("binding_session_mode") or "stateless"

    async def start_invocation(self, **kwargs):
        return SimpleNamespace(id=uuid4(), agent_session_id=None)

    async def complete_invocation(self, invocation_id, *, result, persist_context):
        return None

    async def fail_invocation(self, invocation_id, error, **kwargs):
        raise AssertionError(error)

    async def emit(self, execution_id, event_type, payload, *, invocation_id=None):
        self.events.append((event_type, payload))


class _BlockingRootInvoker:
    def __init__(self, root_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.first_token_emitted = asyncio.Event()
        self.release_completion = asyncio.Event()

    async def invoke(self, *, agent_id, stream_handler=None, **kwargs):
        assert agent_id == self.root_agent_id
        assert stream_handler is not None

        await stream_handler(
            "token",
            {
                "content": "Hello",
                "channel": "final",
                "visibility": "assistant",
                "phase": "response_generation",
            },
        )
        self.first_token_emitted.set()
        await self.release_completion.wait()
        await stream_handler(
            "token",
            {
                "content": " world",
                "channel": "final",
                "visibility": "assistant",
                "phase": "response_generation",
            },
        )
        return AgentInvocationResult(answer="Hello world", streamed_output=True)


def _runtime(root_node_id, root_agent_id):
    definition = {
        "schema_version": 2,
        "root_node_id": str(root_node_id),
        "nodes": [
            {
                "id": str(root_node_id),
                "agent_id": str(root_agent_id),
                "label": "Entry",
                "capability_description": "Coordinates work.",
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
    }
    version = SimpleNamespace(
        kind="release",
        definition=definition,
        resolved_bindings={
            str(root_node_id): {
                "release_id": str(uuid4()),
                "session_mode": "stateless",
            }
        },
    )
    execution = SimpleNamespace(
        id=uuid4(),
        network_id=uuid4(),
        project_id=uuid4(),
        network_session_id=uuid4(),
        network_version_id=uuid4(),
        input_message="run",
        draft_revision=None,
    )
    return execution, version


@pytest.mark.asyncio
async def test_root_token_is_observable_before_network_execution_completes() -> None:
    root_node_id = uuid4()
    root_agent_id = uuid4()
    execution, version = _runtime(root_node_id, root_agent_id)
    store = _EventStore()
    invoker = _BlockingRootInvoker(root_agent_id)
    executor = NetworkExecutor(invoker=invoker, store=store)

    task = asyncio.create_task(executor.execute(execution, version))
    await asyncio.wait_for(invoker.first_token_emitted.wait(), timeout=1)

    assert task.done() is False
    assert [payload["content"] for event, payload in store.events if event == "token"] == [
        "Hello"
    ]

    invoker.release_completion.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result.answer == "Hello world"
    assert [payload["content"] for event, payload in store.events if event == "token"] == [
        "Hello",
        " world",
    ]
