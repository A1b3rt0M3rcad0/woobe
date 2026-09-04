from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1


def _request() -> ContextAssemblyRequest:
    runtime_context = SimpleNamespace(
        model_capacity_units=None,
        reserved_output_units=None,
        active_tool_definitions=[],
        context_selection_metadata={},
        rag_metadata={},
        context_rag_sources=[],
        parent_invocation_id=None,
        network_execution_id=None,
        network_invocation_id=None,
        network_node_id=None,
        input_message_id=None,
        run_id=uuid4(),
    )
    return ContextAssemblyRequest(
        messages=[
            SystemMessage(content="system"),
            HumanMessage(content="current user"),
        ],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="openai",
        model="test-model",
        runtime_context=runtime_context,
        policy=ContextPolicyV1(),
    )


def test_default_context_assembler_implements_behavioral_contract() -> None:
    assembler = DefaultContextAssembler()

    assert isinstance(assembler, ContextAssembler)

    request = _request()
    result = assembler.assemble(request)

    assert [message.content for message in result.messages] == [
        "system",
        "current user",
    ]
    assert result.snapshot.model_invocation_id == request.model_invocation_id
    assert result.snapshot.agent_run_id == request.agent_run_id


class _FakeContextAssembler(ContextAssembler):
    def __init__(self) -> None:
        self.requests: list[ContextAssemblyRequest] = []

    def assemble(self, request: ContextAssemblyRequest):
        self.requests.append(request)
        return SimpleNamespace(messages=["fake-context"], snapshot=object())


def test_context_assembler_contract_is_replaceable_without_default_implementation() -> None:
    assembler = _FakeContextAssembler()
    request = _request()

    result = assembler.assemble(request)

    assert assembler.requests == [request]
    assert result.messages == ["fake-context"]
