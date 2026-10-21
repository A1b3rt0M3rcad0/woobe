from types import SimpleNamespace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

import woobe_workers.composition.network_agent_runtime as runtime_module
from woobe_workers.composition.network_agent_runtime import ProjectRAIAgentInvoker
from shared.security.principal import ProjectApiPrincipal


class _Output:
    answer = "ok"
    session_id = None
    trace_id = None
    provider = "test"
    model = "test"
    usage = None
    tool_calls = []
    sources = []
    parsed_output = None
    output_parse_error = None


@pytest.mark.asyncio
async def test_network_bridge_strips_internal_envelope_and_passes_external_context(
    monkeypatch,
) -> None:
    captured = {}

    class UseCase:
        async def execute(self, input_dto):
            captured["external_context"] = input_dto.external_context
            captured["snapshot_override"] = input_dto.snapshot_override
            captured["principal"] = input_dto.runtime_principal
            captured["metadata"] = input_dto.metadata
            return _Output()

    monkeypatch.setattr(
        runtime_module,
        "build_internal_agent_runtime",
        lambda settings, http_executor: UseCase(),
    )
    invoker = ProjectRAIAgentInvoker(SimpleNamespace(), object())
    snapshot_override = {
        "provider": "openai",
        "model": "gpt-test",
        "__network_external_context__": {"customer_id": "cus-1"},
    }
    principal = ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="runtime",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        target_type="network",
        target_id=uuid4(),
        environment="production",
        interfaces=frozenset({"network", "artifacts"}),
        authenticated_at=datetime.now(UTC),
    )

    result = await invoker.invoke(
        project_id=uuid4(),
        agent_id=uuid4(),
        release_id=None,
        snapshot_override=snapshot_override,
        message="hello",
        agent_session_id=None,
        execution_context="playground",
        internal_tools=[],
        network_context={
            "network_id": str(uuid4()),
            "network_version_id": None,
            "network_session_id": str(uuid4()),
            "network_execution_id": str(uuid4()),
            "network_invocation_id": str(uuid4()),
            "parent_invocation_id": None,
            "network_node_id": str(uuid4()),
            "depth": 0,
            "runtime_principal_snapshot": principal.model_dump(mode="json"),
            "artifact_workspace_binding": {"workspace_id": "workspace-1"},
            "artifact_workspace_policy": {"field": "workspace"},
            "artifact_node_actions": ["read"],
        },
    )

    assert result.answer == "ok"
    assert captured["external_context"] == {"customer_id": "cus-1"}
    assert captured["snapshot_override"] == {
        "provider": "openai",
        "model": "gpt-test",
    }
    assert captured["principal"] == principal
    assert "runtime_principal_snapshot" not in captured["metadata"]
    assert captured["metadata"]["__network_artifact_runtime__"] == {
        "enabled": True,
        "binding": {"workspace_id": "workspace-1"},
        "policy": {"field": "workspace"},
        "node_actions": ["read"],
    }
    assert snapshot_override["__network_external_context__"] == {
        "customer_id": "cus-1"
    }
