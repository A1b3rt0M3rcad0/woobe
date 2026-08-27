from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application import runtime as runtime_module
from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkBudgetExceeded,
    NetworkExecutor,
)


class FakeStore:
    def __init__(self) -> None:
        self.events = []
        self.started = []
        self.completed = []
        self.failed = []

    async def is_cancel_requested(self, execution_id):
        return False

    async def start_invocation(self, **kwargs):
        invocation = SimpleNamespace(
            id=uuid4(),
            agent_session_id=None,
            context_state="stateless",
            previous_invocation_count=0,
        )
        self.started.append((invocation.id, kwargs))
        return invocation

    async def complete_invocation(self, invocation_id, *, result, persist_context):
        self.completed.append((invocation_id, result, persist_context))

    async def fail_invocation(self, invocation_id, error, **kwargs):
        self.failed.append((invocation_id, error, kwargs))

    async def emit(self, execution_id, event_type, payload, *, invocation_id=None):
        self.events.append((event_type, payload, invocation_id))


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
        self.first_result = await internal_tools[0].handler(
            {
                "task": "Inspect the customer issue",
                "context": {"customer_id": "42"},
            }
        )
        # Semantically the same target, but deliberately different wording. The
        # successful child result is already available to this parent invocation.
        self.second_result = await internal_tools[0].handler(
            {
                "task": "Review that same customer's issue again and summarize it",
                "context": {"customer_id": "42"},
            }
        )
        return AgentInvocationResult(answer="root result")


class LinearDelegationInvoker:
    def __init__(self, ordered_agent_ids) -> None:
        self.ordered_agent_ids = list(ordered_agent_ids)
        self.calls = []

    async def invoke(self, *, agent_id, internal_tools, **kwargs):
        self.calls.append(agent_id)
        index = self.ordered_agent_ids.index(agent_id)
        if index == len(self.ordered_agent_ids) - 1:
            return AgentInvocationResult(answer=f"layer-{index + 1}")
        assert len(internal_tools) == 1
        child = await internal_tools[0].handler(
            {"task": f"Continue to layer {index + 2}"}
        )
        assert child["success"] is True
        return AgentInvocationResult(
            answer=f"layer-{index + 1} <- {child['result']}"
        )


class DeadlineAwareInvoker:
    def __init__(self, root_agent_id, child_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.child_agent_id = child_agent_id
        self.child_calls = 0
        self.delegation_result = None

    async def invoke(self, *, agent_id, internal_tools, **kwargs):
        if agent_id == self.child_agent_id:
            self.child_calls += 1
            return AgentInvocationResult(answer="late child")
        self.delegation_result = await internal_tools[0].handler(
            {"task": "Start another expensive delegation"}
        )
        return AgentInvocationResult(answer="final answer from completed evidence")


def _runtime_setup():
    execution, version, agent_ids = _linear_runtime_setup(2)
    return execution, version, agent_ids[0], agent_ids[1]


def _linear_runtime_setup(
    layers: int,
    *,
    max_depth: int = 7,
    max_invocations: int = 16,
    timeout_seconds: int = 30,
):
    assert layers >= 1
    network_id = uuid4()
    project_id = uuid4()
    session_id = uuid4()
    execution_id = uuid4()
    node_ids = [uuid4() for _ in range(layers)]
    agent_ids = [uuid4() for _ in range(layers)]
    release_ids = [uuid4() for _ in range(layers)]

    nodes = []
    bindings = {}
    for index, (node_id, agent_id, release_id) in enumerate(
        zip(node_ids, agent_ids, release_ids, strict=True)
    ):
        nodes.append(
            {
                "id": str(node_id),
                "agent_id": str(agent_id),
                "label": f"Layer {index + 1}",
                "capability_description": f"Handles layer {index + 1}.",
                "position": {"x": index * 220, "y": 0},
                "binding": {"source": "release", "release_id": str(release_id)},
            }
        )
        bindings[str(node_id)] = {
            "release_id": str(release_id),
            "release_version": "v1.0.20260827.01",
            "session_mode": "stateless",
        }

    edges = [
        {
            "id": str(uuid4()),
            "source_node_id": str(node_ids[index]),
            "target_node_id": str(node_ids[index + 1]),
        }
        for index in range(layers - 1)
    ]
    definition = {
        "schema_version": 2,
        "root_node_id": str(node_ids[0]),
        "nodes": nodes,
        "edges": edges,
        "settings": {
            "session_mode": "stateless",
            "max_depth": max_depth,
            "max_invocations": max_invocations,
            "timeout_seconds": timeout_seconds,
        },
    }
    version = SimpleNamespace(
        kind="release",
        definition=definition,
        resolved_bindings=bindings,
    )
    execution = SimpleNamespace(
        id=execution_id,
        network_id=network_id,
        project_id=project_id,
        network_session_id=session_id,
        network_version_id=uuid4(),
        input_message="Execute the complete chain",
        draft_revision=None,
    )
    return execution, version, agent_ids


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
async def test_successful_target_is_not_reinvoked_by_same_parent_even_with_new_wording() -> None:
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
    assert invoker.second_result["error_code"] == "duplicate_successful_delegation"
    skipped = [
        payload for event_type, payload, _ in store.events
        if event_type == "delegation_skipped"
    ]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "already_completed_successfully"


@pytest.mark.asyncio
async def test_network_executes_seven_layers_in_order() -> None:
    execution, version, agent_ids = _linear_runtime_setup(
        7,
        max_depth=7,
        max_invocations=16,
    )
    store = FakeStore()
    invoker = LinearDelegationInvoker(agent_ids)

    result = await NetworkExecutor(invoker=invoker, store=store).execute(
        execution,
        version,
    )

    assert invoker.calls == agent_ids
    assert len(store.started) == 7
    assert len(store.completed) == 7
    assert not store.failed
    assert result.answer.startswith("layer-1 <- layer-2")
    completed_delegations = [
        payload for event_type, payload, _ in store.events
        if event_type == "delegation_completed"
    ]
    assert len(completed_delegations) == 6


@pytest.mark.asyncio
async def test_network_rejects_layer_beyond_configured_depth() -> None:
    execution, version, agent_ids = _linear_runtime_setup(
        8,
        max_depth=6,
        max_invocations=16,
    )
    invoker = LinearDelegationInvoker(agent_ids)

    with pytest.raises(NetworkBudgetExceeded) as captured:
        await NetworkExecutor(invoker=invoker, store=FakeStore()).execute(
            execution,
            version,
        )

    assert captured.value.code == "network_max_depth_exceeded"


@pytest.mark.asyncio
async def test_network_reports_invocation_budget_separately_from_depth() -> None:
    execution, version, agent_ids = _linear_runtime_setup(
        2,
        max_depth=7,
        max_invocations=1,
    )
    invoker = LinearDelegationInvoker(agent_ids)

    with pytest.raises(NetworkBudgetExceeded) as captured:
        await NetworkExecutor(invoker=invoker, store=FakeStore()).execute(
            execution,
            version,
        )

    assert captured.value.code == "network_max_invocations_exceeded"


@pytest.mark.asyncio
async def test_deadline_reserve_blocks_new_delegation_and_preserves_parent_synthesis(
    monkeypatch,
) -> None:
    execution, version, agent_ids = _linear_runtime_setup(
        2,
        timeout_seconds=30,
    )
    ticks = iter([0.0, 0.0, 29.0])
    monkeypatch.setattr(runtime_module.time, "monotonic", lambda: next(ticks, 29.0))
    store = FakeStore()
    invoker = DeadlineAwareInvoker(agent_ids[0], agent_ids[1])

    result = await NetworkExecutor(invoker=invoker, store=store).execute(
        execution,
        version,
    )

    assert result.answer == "final answer from completed evidence"
    assert invoker.child_calls == 0
    assert invoker.delegation_result["error_code"] == "network_deadline_near"
    skipped = [
        payload for event_type, payload, _ in store.events
        if event_type == "delegation_skipped"
    ]
    assert skipped[-1]["reason"] == "network_deadline_near"
