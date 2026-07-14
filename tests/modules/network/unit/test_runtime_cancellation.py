import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionCancelled,
    NetworkExecutor,
)


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

    async def complete_invocation(self, _invocation_id, *, result) -> None:
        self.completed = result.answer == "late answer"

    async def fail_invocation(self, _invocation_id, _error) -> None:
        self.failed = True

    async def emit(self, *_args, **_kwargs) -> None:
        return None


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
