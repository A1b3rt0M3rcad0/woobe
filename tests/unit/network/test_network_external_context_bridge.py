from types import SimpleNamespace
from uuid import uuid4

import pytest

import woobe_workers.composition.network_agent_runtime as runtime_module
from woobe_workers.composition.network_agent_runtime import ProjectRAIAgentInvoker


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
        },
    )

    assert result.answer == "ok"
    assert captured["external_context"] == {"customer_id": "cus-1"}
    assert captured["snapshot_override"] == {
        "provider": "openai",
        "model": "gpt-test",
    }
    assert snapshot_override["__network_external_context__"] == {
        "customer_id": "cus-1"
    }
