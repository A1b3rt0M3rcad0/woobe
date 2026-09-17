import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionCancelled,
    NetworkExecutor,
    delegation_tool_description,
)
from modules.network.domain.entities import NetworkNode


class _Invoker:
    async def invoke(self, **_kwargs) -> AgentInvocationResult:
        return AgentInvocationResult(answer="late answer")


class _Store:
    def __init__(self) -> None:
        self.cancel_checks = 0
        self.completed = False
        self.failed = False

    async def is_cancel_requested(self, _execution_id) -> bool:
        self.cancel_checks += 1
        return self.cancel_checks > 1

    async def start_invocation(self, **_kwargs):
        return SimpleNamespace(id=uuid4(), agent_session_id=None)

    async def complete_invocation(
        self,
        _invocation_id,
        *,
        result,
        persist_context: bool,
    ) -> None:
        assert persist_context is True
        self.completed = result.answer == "late answer"

    async def fail_invocation(self, _invocation_id, _error) -> None:
        self.failed = True

    async def emit(self, *_args, **_kwargs) -> None:
        return None


def test_delegation_tool_exposes_the_versioned_agent_capability() -> None:
    node = NetworkNode(
        id=uuid4(),
        agent_id=uuid4(),
        label="Billing specialist",
        capability_description=(
            "Investigates invoices, duplicate charges, and payment disputes."
        ),
    )

    description = delegation_tool_description(node)

    assert "Billing specialist" in description
    assert "duplicate charges" in description
    assert "system prompt" not in description.lower()


def test_cancellation_after_agent_call_discards_network_result() -> None:
    node_id = uuid4()
    agent_id = uuid4()
    store = _Store()
    executor = NetworkExecutor(invoker=_Invoker(), store=store)
    execution = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        input_message="work",
    )
    version = SimpleNamespace(
        kind="staging",
        definition={
            "schema_version": 1,
            "root_node_id": str(node_id),
            "nodes": [
                {
                    "id": str(node_id),
                    "agent_id": str(agent_id),
                    "label": "Root",
                }
            ],
            "edges": [],
            "settings": {
                "session_mode": "stateful",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 90,
            },
        },
        resolved_bindings={str(node_id): {"release_id": str(uuid4())}},
    )

    async def run() -> None:
        with pytest.raises(NetworkExecutionCancelled):
            await executor.execute(execution, version)

    asyncio.run(run())

    assert store.completed is True
    assert store.failed is False


def test_draft_execution_uses_captured_snapshot_without_network_version() -> None:
    node_id = uuid4()
    agent_id = uuid4()
    captured: dict = {}

    class DraftInvoker:
        async def invoke(self, **kwargs) -> AgentInvocationResult:
            captured.update(kwargs)
            return AgentInvocationResult(answer="draft answer")

    class DraftStore(_Store):
        async def is_cancel_requested(self, _execution_id) -> bool:
            return False

        async def complete_invocation(
            self,
            _invocation_id,
            *,
            result,
            persist_context: bool,
        ) -> None:
            assert persist_context is True
            self.completed = result.answer == "draft answer"

    execution = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        input_message="test the draft",
        draft_revision=7,
        definition_snapshot={
            "schema_version": 1,
            "root_node_id": str(node_id),
            "nodes": [
                {
                    "id": str(node_id),
                    "agent_id": str(agent_id),
                    "label": "Draft Agent",
                }
            ],
            "edges": [],
            "settings": {
                "session_mode": "stateful",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 90,
                "max_tool_result_chars": 24_000,
            },
        },
        resolved_bindings_snapshot={
            str(node_id): {
                "agent_id": str(agent_id),
                "snapshot_override": {
                    "system_prompt": "Draft prompt",
                    "model": "draft-model",
                },
            }
        },
    )

    async def run() -> None:
        executor = NetworkExecutor(invoker=DraftInvoker(), store=DraftStore())
        result = await executor.execute(execution, None)
        assert result.answer == "draft answer"

    asyncio.run(run())

    assert captured["release_id"] is None
    assert captured["execution_context"] == "playground"
    assert captured["snapshot_override"]["system_prompt"] == "Draft prompt"
    assert captured["network_context"]["draft_revision"] == 7
    assert captured["network_context"]["tool_result_max_chars"] == 24_000


def test_stateless_network_does_not_persist_agent_context() -> None:
    node_id = uuid4()
    agent_id = uuid4()
    persistence: dict[str, bool] = {}

    class StatelessInvoker:
        async def invoke(self, **_kwargs) -> AgentInvocationResult:
            return AgentInvocationResult(answer="stateless answer", session_id=uuid4())

    class StatelessStore(_Store):
        async def is_cancel_requested(self, _execution_id) -> bool:
            return False

        async def start_invocation(self, **kwargs):
            persistence["start"] = kwargs["persist_context"]
            return SimpleNamespace(id=uuid4(), agent_session_id=None)

        async def complete_invocation(
            self,
            _invocation_id,
            *,
            result,
            persist_context: bool,
        ) -> None:
            persistence["complete"] = persist_context
            self.completed = result.answer == "stateless answer"

    execution = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        input_message="no shared context",
    )
    version = SimpleNamespace(
        kind="staging",
        definition={
            "schema_version": 1,
            "root_node_id": str(node_id),
            "nodes": [
                {"id": str(node_id), "agent_id": str(agent_id), "label": "Root"}
            ],
            "edges": [],
            "settings": {
                "session_mode": "stateless",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 90,
            },
        },
        resolved_bindings={str(node_id): {"release_id": str(uuid4())}},
    )

    async def run() -> None:
        executor = NetworkExecutor(invoker=StatelessInvoker(), store=StatelessStore())
        result = await executor.execute(execution, version)
        assert result.answer == "stateless answer"

    asyncio.run(run())

    assert persistence == {"start": False, "complete": False}
