from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.context_managers import standard
from modules.agent.application.context_managers.standard import StandardContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.context import ContextSnapshot
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)


def _request() -> ContextAssemblyRequest:
    runtime_context = new_execution_context()
    runtime_context.run_id = uuid4()
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


def test_standard_context_assembler_implements_behavioral_contract() -> None:
    assembler = StandardContextAssembler()

    assert isinstance(assembler, ContextAssembler)

    request = _request()
    result = assembler.assemble(request)

    assert [message.content for message in result.messages] == [
        "system",
        "current user",
    ]
    assert result.snapshot.model_invocation_id == request.model_invocation_id
    assert result.snapshot.agent_run_id == request.agent_run_id


def test_standard_context_assembler_is_transparent_adapter(monkeypatch) -> None:
    request = _request()
    captured: dict[str, Any] = {}
    sentinel = cast(ContextAssemblyOutput, object())

    def fake_assemble_context(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        standard,
        "assemble_context",
        fake_assemble_context,
    )

    result = StandardContextAssembler().assemble(request)

    assert result is sentinel
    assert captured == {
        "messages": request.messages,
        "model_invocation_id": request.model_invocation_id,
        "agent_run_id": request.agent_run_id,
        "project_id": request.project_id,
        "provider": request.provider,
        "model": request.model,
        "runtime_context": request.runtime_context,
        "policy": request.policy,
    }


@dataclass(frozen=True, slots=True)
class _FakeAssemblyOutput:
    messages: list[Any]
    snapshot: ContextSnapshot


class _FakeContextAssembler(ContextAssembler):
    def __init__(self) -> None:
        self.requests: list[ContextAssemblyRequest] = []
        self.snapshot = cast(ContextSnapshot, object())
        self.capacity_seen: int | None = None
        self.tool_definitions_seen: list[dict[str, Any]] | None = None

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        self.requests.append(request)
        self.capacity_seen = request.runtime_context.model_capacity_units
        active_tools = request.runtime_context.active_tool_definitions
        self.tool_definitions_seen = list(active_tools) if active_tools is not None else None
        return _FakeAssemblyOutput(
            messages=["fake-context"],
            snapshot=self.snapshot,
        )


class _FailingContextAssembler:
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raise RuntimeError("context assembly failed")


def test_context_assembler_contract_is_replaceable_without_standard_implementation() -> None:
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
    capability = ContextAssemblyCapability(
        assembler=assembler,
        provider="openai",
        model_name="replacement-model",
        pricing_snapshot={"context_window": 8192},
    )

    token = current_execution.set(context)
    try:
        result = capability.assemble(
            invocation_id=invocation_id,
            messages=original_messages,
            phase="response_generation",
        )
    finally:
        current_execution.reset(token)

    assert list(result.messages) == ["fake-context"]
    assert result.snapshot is assembler.snapshot
    assert len(assembler.requests) == 1
    request = assembler.requests[0]
    assert request.messages == original_messages
    assert request.model_invocation_id == invocation_id
    assert request.agent_run_id == context.run_id
    assert request.project_id == context.project_id
    assert request.provider == "openai"
    assert request.model == "replacement-model"
    assert assembler.capacity_seen == 8192
    assert assembler.tool_definitions_seen == [{"type": "function"}]
    assert context.model_capacity_units == 2048
    assert context.active_tool_definitions == [{"type": "function"}]


@pytest.mark.parametrize("phase", ["final_response_generation", "json_repair"])
def test_terminal_invocations_hide_tools_from_context_assembly_and_restore_state(
    phase: str,
) -> None:
    assembler = _FakeContextAssembler()
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.context_policy = ContextPolicyV1().model_dump(mode="json")
    context.active_tool_definitions = [
        {"type": "function", "function": {"name": "lookup"}}
    ]
    capability = ContextAssemblyCapability(
        assembler=assembler,
        provider="openai",
        model_name="model",
        pricing_snapshot=None,
    )

    token = current_execution.set(context)
    try:
        capability.assemble(
            invocation_id=uuid4(),
            messages=[HumanMessage(content="original")],
            phase=phase,
        )
    finally:
        current_execution.reset(token)

    assert assembler.tool_definitions_seen == []
    assert context.active_tool_definitions == [
        {"type": "function", "function": {"name": "lookup"}}
    ]


def test_invocation_runtime_state_is_restored_when_context_assembler_fails() -> None:
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.context_policy = ContextPolicyV1().model_dump(mode="json")
    context.model_capacity_units = 2048
    context.active_tool_definitions = [
        {"type": "function", "function": {"name": "lookup"}}
    ]
    capability = ContextAssemblyCapability(
        assembler=_FailingContextAssembler(),
        provider="openai",
        model_name="replacement-model",
        pricing_snapshot={"context_window": 8192},
    )

    token = current_execution.set(context)
    try:
        with pytest.raises(RuntimeError, match="context assembly failed"):
            capability.assemble(
                invocation_id=uuid4(),
                messages=[HumanMessage(content="original")],
                phase="final_response_generation",
            )
    finally:
        current_execution.reset(token)

    assert context.model_capacity_units == 2048
    assert context.active_tool_definitions == [
        {"type": "function", "function": {"name": "lookup"}}
    ]


def test_instrumented_context_requires_explicit_assembler_when_execution_is_bound() -> None:
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.context_policy = ContextPolicyV1().model_dump(mode="json")
    capability = ContextAssemblyCapability(
        assembler=None,
        provider="openai",
        model_name="model",
        pricing_snapshot=None,
    )

    token = current_execution.set(context)
    try:
        with pytest.raises(RuntimeError, match="ContextAssembler dependency is required"):
            capability.assemble(
                invocation_id=uuid4(),
                messages=[HumanMessage(content="original")],
                phase="response_generation",
            )
    finally:
        current_execution.reset(token)
