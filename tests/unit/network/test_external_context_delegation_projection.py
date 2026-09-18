from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.external_context_contract import compose_external_context_contracts
from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
    NetworkExecutor,
)
from modules.network.infra.runtime.loader import NetworkRuntimeLoader


NETWORK_CONTEXT_KEY = "__network_external_context__"


class _Store:
    def __init__(self) -> None:
        self.invocations = []

    async def is_cancel_requested(self, execution_id):
        return False

    async def resolve_agent_session_mode(self, **kwargs):
        return kwargs.get("binding_session_mode") or "stateless"

    async def start_invocation(self, **kwargs):
        invocation = SimpleNamespace(
            id=uuid4(),
            agent_session_id=None,
            context_state="stateless",
            previous_invocation_count=0,
        )
        self.invocations.append((kwargs, invocation))
        return invocation

    async def complete_invocation(self, invocation_id, *, result, persist_context):
        return None

    async def fail_invocation(self, invocation_id, error, **kwargs):
        raise AssertionError(error)

    async def emit(self, execution_id, event_type, payload, *, invocation_id=None):
        return None


class _CapturingDelegatingInvoker:
    def __init__(self, root_agent_id, child_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.child_agent_id = child_agent_id
        self.received: dict[str, dict] = {}

    async def invoke(
        self,
        *,
        agent_id,
        snapshot_override,
        internal_tools,
        **_kwargs,
    ):
        self.received[str(agent_id)] = dict(snapshot_override or {})
        if agent_id == self.child_agent_id:
            return AgentInvocationResult(answer="child")

        assert agent_id == self.root_agent_id
        delegated = await internal_tools[0].handler({"task": "resolve specialist"})
        assert delegated["result"] == "child"
        return AgentInvocationResult(answer="root")


def _field(*, expose: bool) -> dict:
    return {
        "schema": {"type": "string"},
        "required": True,
        "scope": "session",
        "model": {"expose": expose},
    }


@pytest.mark.asyncio
async def test_root_and_child_receive_only_their_projected_external_context() -> None:
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
                "label": "Root",
                "capability_description": "Coordinates.",
                "position": {"x": 0, "y": 0},
                "binding": {"source": "draft"},
            },
            {
                "id": str(child_node_id),
                "agent_id": str(child_agent_id),
                "label": "Specialist",
                "capability_description": "Resolves specialist work.",
                "position": {"x": 300, "y": 0},
                "binding": {"source": "draft"},
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
    effective = compose_external_context_contracts(
        {
            str(root_node_id): {
                "name": _field(expose=True),
            },
            str(child_node_id): {
                "customer_id": _field(expose=False),
            },
        }
    )
    source_bindings = {
        str(root_node_id): {
            "session_mode": "stateless",
            "snapshot_override": {
                "provider": "custom",
                "model": "root-model",
            },
        },
        str(child_node_id): {
            "session_mode": "stateless",
            "snapshot_override": {
                "provider": "custom",
                "model": "child-model",
            },
        },
    }
    bound = NetworkRuntimeLoader._bind_external_context(
        source_bindings,
        effective,
        {
            "name": "Alberto",
            "customer_id": "cus-123",
        },
    )

    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="run",
        draft_revision=1,
        definition_snapshot=definition,
        resolved_bindings_snapshot=bound,
        status="running",
    )
    invoker = _CapturingDelegatingInvoker(root_agent_id, child_agent_id)

    result = await NetworkExecutor(invoker=invoker, store=_Store()).execute(
        execution,
        version=None,
    )

    assert result.answer == "root"
    assert invoker.received[str(root_agent_id)][NETWORK_CONTEXT_KEY] == {
        "name": "Alberto"
    }
    assert invoker.received[str(child_agent_id)][NETWORK_CONTEXT_KEY] == {
        "customer_id": "cus-123"
    }
    assert "customer_id" not in invoker.received[str(root_agent_id)][NETWORK_CONTEXT_KEY]
    assert "name" not in invoker.received[str(child_agent_id)][NETWORK_CONTEXT_KEY]
