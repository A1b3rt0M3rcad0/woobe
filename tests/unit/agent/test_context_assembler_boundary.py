from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution.execution_instrumentation import (
    _assemble_invocation_context,
)


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
        self.snapshot = object()
        self.capacity_seen: int | None = None

    def assemble(self, request: ContextAssemblyRequest):
        self.requests.append(request)
        self.capacity_seen = request.runtime_context.model_capacity_units
        return SimpleNamespace(messages=["fake-context"], snapshot=self.snapshot)


def test_context_assembler_contract_is_replaceable_without_default_implementation() -> None:
    assembler = _FakeContextAssembler()
    request = _request()

    result = assembler.assemble(request)

    assert assembler.requests == [request]
    assert result.messages == ["fake-context"]


def test_invocation_context_uses_injected_context_assembler() -> None:
    assembler = _FakeContextAssembler()
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.context_policy = ContextPolicyV1().model_dump(mode="json")
    context.model_capacity_units = 2048
    context.active_tool_definitions = [{"type": "function"}]
    invocation_id = uuid4()
    original_messages = [HumanMessage(content="original")]

    token = current_execution.set(context)
    try:
        messages, snapshot = _assemble_invocation_context(
            invocation_id=invocation_id,
            messages=original_messages,
            provider="openai",
            model_name="replacement-model",
            phase="response_generation",
            pricing_snapshot={"context_window": 8192},
            context_assembler=assembler,
        )
    finally:
        current_execution.reset(token)

    assert messages == ["fake-context"]
    assert snapshot is assembler.snapshot
    assert len(assembler.requests) == 1
    request = assembler.requests[0]
    assert request.messages == original_messages
    assert request.model_invocation_id == invocation_id
    assert request.agent_run_id == context.run_id
    assert request.project_id == context.project_id
    assert request.provider == "openai"
    assert request.model == "replacement-model"
    assert assembler.capacity_seen == 8192
    assert context.model_capacity_units == 2048
    assert context.active_tool_definitions == [{"type": "function"}]


def test_instrumented_context_requires_explicit_assembler_when_execution_is_bound() -> None:
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.context_policy = ContextPolicyV1().model_dump(mode="json")

    token = current_execution.set(context)
    try:
        with pytest.raises(RuntimeError, match="ContextAssembler dependency is required"):
            _assemble_invocation_context(
                invocation_id=uuid4(),
                messages=[HumanMessage(content="original")],
                provider="openai",
                model_name="model",
                phase="response_generation",
                pricing_snapshot=None,
                context_assembler=None,
            )
    finally:
        current_execution.reset(token)
