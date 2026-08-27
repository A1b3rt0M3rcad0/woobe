from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import AgentInvocationResult, NetworkExecutor


class FakeStore:
    def __init__(self) -> None:
        self.events = []

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


class FakeInvoker:
    def __init__(self, root_agent_id, specialist_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.specialist_agent_id = specialist_agent_id
        self.delegation_result = None

    async def invoke(self, *, agent_id, internal_tools, **kwargs):
        if agent_id == self.specialist_agent_id:
            return AgentInvocationResult(
                answer='{"sentiment":"negative","confidence":0.91}',
                parsed_output={"sentiment": "negative", "confidence": 0.91},
            )
        assert agent_id == self.root_agent_id
        self.delegation_result = await internal_tools[0].handler(
            {"task": "Classify the customer sentiment"}
        )
        return AgentInvocationResult(
            answer="The customer sentiment is negative.",
            parsed_output={"answer": "negative"},
        )


class DuplicateDelegationInvoker:
    def __init__(self, root_agent_id, specialist_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.specialist_agent_id = specialist_agent_id
        self.specialist_calls = 0
        self.first_result = None
        self.second_result = None

    async def invoke(self, *, agent_id, internal_tools, **kwargs):
        if agent_id == self.specialist_agent_id:
            self.specialist_calls += 1
            return AgentInvocationResult(answer="specialist result")
        assert agent_id == self.root_agent_id
        arguments = {
            "task": "Inspect the same customer issue",
            "context": {"customer_id": "42"},
        }
        self.first_result = await internal_tools[0].handler(arguments)
        self.second_result = await internal_tools[0].handler(arguments)
        return AgentInvocationResult(answer="root result")


def _runtime_setup():
    network_id = uuid4()
    project_id = uuid4()
    session_id = uuid4()
    execution_id = uuid4()
    root_node_id = uuid4()
    specialist_node_id = uuid4()
    root_agent_id = uuid4()
    specialist_agent_id = uuid4()
    root_release_id = uuid4()
    specialist_release_id = uuid4()

    definition = {
        "schema_version": 2,
        "root_node_id": str(root_node_id),
        "nodes": [
            {
                "id": str(root_node_id),
                "agent_id": str(root_agent_id),
                "label": "Entry",
                "capability_description": "Coordinates the response.",
                "position": {"x": 0, "y": 0},
                "binding": {"source": "release", "release_id": str(root_release_id)},
            },
            {
                "id": str(specialist_node_id),
                "agent_id": str(specialist_agent_id),
                "label": "Sentiment Specialist",
                "capability_description": "Classifies sentiment.",
                "position": {"x": 300, "y": 0},
                "binding": {
                    "source": "release",
                    "release_id": str(specialist_release_id),
                },
            },
        ],
        "edges": [
            {
                "id": str(uuid4()),
                "source_node_id": str(root_node_id),
                "target_node_id": str(specialist_node_id),
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
                "release_id": str(root_release_id),
                "release_version": "v1.0.20260715.01",
                "session_mode": "stateless",
            },
            str(specialist_node_id): {
                "release_id": str(specialist_release_id),
                "release_version": "v1.0.20260715.01",
                "session_mode": "stateless",
            },
        },
    )
    execution = SimpleNamespace(
        id=execution_id,
        network_id=network_id,
        project_id=project_id,
        network_session_id=session_id,
        network_version_id=uuid4(),
        input_message="How does the customer feel?",
        draft_revision=None,
    )
    return execution, version, root_agent_id, specialist_agent_id


@pytest.mark.asyncio
async def test_specialist_parsed_output_is_returned_as_tool_result_object() -> None:
    execution, version, root_agent_id, specialist_agent_id = _runtime_setup()
    invoker = FakeInvoker(root_agent_id, specialist_agent_id)
    result = await NetworkExecutor(invoker=invoker, store=FakeStore()).execute(
        execution,
        version,
    )

    assert result.parsed_output == {"answer": "negative"}
    assert invoker.delegation_result == {
        "success": True,
        "result_type": "structured",
        "result": {"sentiment": "negative", "confidence": 0.91},
    }


@pytest.mark.asyncio
async def test_equivalent_delegation_is_skipped_without_second_agent_run() -> None:
    execution, version, root_agent_id, specialist_agent_id = _runtime_setup()
    store = FakeStore()
    invoker = DuplicateDelegationInvoker(root_agent_id, specialist_agent_id)

    result = await NetworkExecutor(invoker=invoker, store=store).execute(
        execution,
        version,
    )

    assert result.answer == "root result"
    assert invoker.specialist_calls == 1
    assert invoker.first_result == {
        "success": True,
        "result_type": "text",
        "result": "specialist result",
    }
    assert invoker.second_result["success"] is False
    assert invoker.second_result["error_code"] == "duplicate_delegation"
    skipped = [payload for event_type, payload in store.events if event_type == "delegation_skipped"]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "duplicate_delegation"
