from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import AgentInvocationResult, NetworkExecutor


class EventStore:
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


class StreamingInvoker:
    def __init__(self, root_agent_id, child_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.child_agent_id = child_agent_id

    async def invoke(self, *, agent_id, internal_tools, stream_handler=None, **kwargs):
        if agent_id == self.child_agent_id:
            await stream_handler(
                "token",
                {"content": "child output", "channel": "final", "visibility": "assistant"},
            )
            return AgentInvocationResult(answer="child output", streamed_output=True)

        assert agent_id == self.root_agent_id
        child_result = await internal_tools[0].handler({"task": "provide input"})
        assert child_result["result"] == "child output"
        await stream_handler(
            "token",
            {"content": "public output", "channel": "final", "visibility": "assistant"},
        )
        return AgentInvocationResult(answer="public output", streamed_output=True)


@pytest.mark.asyncio
async def test_only_root_tokens_are_emitted_to_network_stream() -> None:
    root_node_id = uuid4()
    child_node_id = uuid4()
    root_agent_id = uuid4()
    child_agent_id = uuid4()
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
            },
            {
                "id": str(child_node_id),
                "agent_id": str(child_agent_id),
                "label": "Specialist",
                "capability_description": "Provides focused input.",
                "position": {"x": 300, "y": 0},
                "binding": {"source": "release", "release_id": str(uuid4())},
            },
        ],
        "edges": [
            {
                "id": str(uuid4()),
                "source_node_id": str(root_node_id),
                "target_node_id": str(child_node_id),
            }
        ],
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
            },
            str(child_node_id): {
                "release_id": str(uuid4()),
                "session_mode": "stateless",
            },
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
    store = EventStore()

    result = await NetworkExecutor(
        invoker=StreamingInvoker(root_agent_id, child_agent_id),
        store=store,
    ).execute(execution, version)

    assert result.answer == "public output"
    assert [payload["content"] for event, payload in store.events if event == "token"] == [
        "public output"
    ]
