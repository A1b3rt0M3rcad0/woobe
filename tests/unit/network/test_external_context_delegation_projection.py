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
    def __init__(self, root_agent_id, child_agent_ids) -> None:
        self.root_agent_id = root_agent_id
        self.child_agent_ids = set(child_agent_ids)
        self.received: dict[str, dict] = {}
        self.network_contexts: dict[str, dict] = {}
        self.content_parts: dict[str, object] = {}

    async def invoke(
        self,
        *,
        agent_id,
        snapshot_override,
        internal_tools,
        network_context,
        **_kwargs,
    ):
        self.received[str(agent_id)] = dict(snapshot_override or {})
        self.network_contexts[str(agent_id)] = dict(network_context)
        self.content_parts[str(agent_id)] = _kwargs.get("content_parts")
        if agent_id in self.child_agent_ids:
            return AgentInvocationResult(answer="child")

        assert agent_id == self.root_agent_id
        delegated = [
            await tool.handler({"task": "resolve specialist"})
            for tool in internal_tools
        ]
        assert all(result["result"] == "child" for result in delegated)
        return AgentInvocationResult(answer="root")


def _field(*, expose: bool) -> dict:
    return {
        "schema": {"type": "string"},
        "required": True,
        "model": {"expose": expose},
    }


@pytest.mark.asyncio
async def test_root_and_child_receive_only_their_projected_external_context() -> None:
    root_node_id = uuid4()
    child_node_id = uuid4()
    denied_node_id = uuid4()
    root_agent_id = uuid4()
    child_agent_id = uuid4()
    denied_agent_id = uuid4()

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
                "artifact_actions": ["write"],
            },
            {
                "id": str(child_node_id),
                "agent_id": str(child_agent_id),
                "label": "Specialist",
                "capability_description": "Resolves specialist work.",
                "position": {"x": 300, "y": 0},
                "binding": {"source": "draft"},
                "artifact_actions": ["read"],
            },
            {
                "id": str(denied_node_id),
                "agent_id": str(denied_agent_id),
                "label": "No Artifacts",
                "position": {"x": 600, "y": 0},
                "binding": {"source": "draft"},
            },
        ],
        "edges": [
            {
                "id": str(uuid4()),
                "source_node_id": str(root_node_id),
                "target_node_id": str(child_node_id),
            },
            {
                "id": str(uuid4()),
                "source_node_id": str(root_node_id),
                "target_node_id": str(denied_node_id),
            }
        ],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 4,
            "max_invocations": 16,
            "timeout_seconds": 30,
            "artifacts_enabled": True,
            "artifact_workspace_binding": {
                "field": "customer_id",
                "namespace": "customer-documents",
                "scope": "session",
                "actions": ["read", "search", "write"],
            },
        },
    }
    effective = compose_external_context_contracts(
        {
            str(root_node_id): {
                "name": _field(expose=True),
                "customer_id": _field(expose=False),
            },
            str(child_node_id): {
                "customer_id": _field(expose=False),
            },
            str(denied_node_id): {
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
        str(denied_node_id): {
            "session_mode": "stateless",
            "snapshot_override": {"provider": "custom", "model": "denied-model"},
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
        input_content_parts=(
            {
                "type": "artifact",
                "ref": {"artifact_id": "doc-1", "revision_id": "doc-rev-1"},
            },
        ),
        artifact_workspace_binding={
            "schema_version": 1,
            "workspace_id": "workspace-fixed",
            "catalog_version": 42,
            "binding_scope": "session",
            "actions": ["read", "search", "write"],
        },
        runtime_principal_snapshot={"kind": "runtime"},
    )
    invoker = _CapturingDelegatingInvoker(root_agent_id, [child_agent_id, denied_agent_id])

    result = await NetworkExecutor(invoker=invoker, store=_Store()).execute(
        execution,
        version=None,
    )

    assert result.answer == "root"
    assert invoker.received[str(root_agent_id)][NETWORK_CONTEXT_KEY] == {
        "name": "Alberto",
        "customer_id": "cus-123",
    }
    assert invoker.received[str(child_agent_id)][NETWORK_CONTEXT_KEY] == {
        "customer_id": "cus-123"
    }
    assert "name" not in invoker.received[str(child_agent_id)][NETWORK_CONTEXT_KEY]
    for agent_id in (root_agent_id, child_agent_id, denied_agent_id):
        assert invoker.network_contexts[str(agent_id)]["artifact_workspace_binding"][
            "workspace_id"
        ] == "workspace-fixed"
    assert invoker.network_contexts[str(root_agent_id)]["artifact_node_actions"] == ["write"]
    assert invoker.content_parts[str(root_agent_id)] == execution.input_content_parts
    assert invoker.content_parts[str(child_agent_id)] is None
    assert invoker.network_contexts[str(child_agent_id)]["artifact_node_actions"] == ["read"]
    assert invoker.network_contexts[str(denied_agent_id)]["artifact_node_actions"] == []
    assert invoker.network_contexts[str(denied_agent_id)]["runtime_principal_snapshot"] == {
        "kind": "runtime"
    }
