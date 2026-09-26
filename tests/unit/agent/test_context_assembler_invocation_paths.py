from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.infra.execution import structured_json_repair, tool_execution_loop
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)


class _UnusedContextAssembler(ContextAssembler):
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raise AssertionError("The propagation test must not invoke context assembly directly")


@pytest.mark.asyncio
async def test_tool_loop_does_not_propagate_context_assembler_into_model_invocations(
    monkeypatch,
) -> None:
    context_assembler = _UnusedContextAssembler()
    prepared_flags: list[bool] = []
    planned_results = [
        SimpleNamespace(
            content="",
            tool_calls=[{"id": "tool-1", "name": "lookup", "args": {"value": "a"}}],
        ),
        SimpleNamespace(
            content="",
            tool_calls=[{"id": "tool-2", "name": "lookup", "args": {"value": "b"}}],
        ),
        SimpleNamespace(content="Need the exact identifier.", tool_calls=[]),
    ]

    async def fake_invoke_llm(**kwargs):
        prepared_flags.append(bool(kwargs.get("context_prepared")))
        assert "context_assembler" not in kwargs
        result = planned_results[len(prepared_flags) - 1]
        return result, {
            "phase": kwargs["phase"],
            "occurred_at": "2026-09-04T00:00:00+00:00",
            "status": "success",
        }

    async def fake_execute_tool_call(*, tool_call, **_kwargs):
        info = ToolCallInfo(
            tool_call_id=tool_call["id"],
            tool_name=tool_call["name"],
            input=tool_call["args"],
            output={"success": False, "error": "not found"},
            success=False,
            status="error",
            error_code="not_found",
            error="not found",
        )
        message = ToolMessage(content="failed", tool_call_id=tool_call["id"])
        return info, message, {
            "occurred_at": "2026-09-04T00:00:00+00:00",
            "success": False,
        }

    monkeypatch.setattr(tool_execution_loop, "invoke_llm", fake_invoke_llm)
    monkeypatch.setattr(tool_execution_loop, "execute_tool_call", fake_execute_tool_call)

    recovery_model = object()
    execution, _call_index = await tool_execution_loop.run_tool_loop(
        model=object(),
        final_model=recovery_model,
        execute_single_tool=lambda *_args, **_kwargs: None,
        messages=[HumanMessage(content="Find the resource")],
        tool_name_to_id={"lookup": "lookup"},
        provider="custom",
        model_name="test-model",
        initial_phase="capability_response_generation",
        final_json_instruction=None,
        context_assembler=context_assembler,
    )

    assert prepared_flags == [True, True, True]
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
        "final_response_generation",
    ]


class _RepairFactory:
    def create_chat_model(self, **_kwargs):
        return object()


@pytest.mark.asyncio
async def test_json_repair_uses_preassembled_context(monkeypatch) -> None:
    context_assembler = _UnusedContextAssembler()
    captured = {}

    async def fake_invoke(self, **kwargs):
        captured.update(kwargs)
        captured["model"] = self.model
        captured["provider"] = self.provider
        captured["model_name"] = self.model_name
        return AIMessage(content='{"ok": true}'), {
            "phase": kwargs["phase"],
            "occurred_at": "2026-09-04T00:00:00+00:00",
            "status": "success",
        }

    monkeypatch.setattr(ModelInvocationCapability, "invoke", fake_invoke)

    execution = InstrumentedExecution(result=AIMessage(content="not-json"))
    result = await structured_json_repair.repair_json_if_needed(
        execution=execution,
        call_index=1,
        llm_factory=_RepairFactory(),
        provider="custom",
        model_name="test-model",
        api_key="test-key",
        base_url=None,
        max_tokens=128,
        schema={"type": "object"},
        clean_json_answer=lambda value: value,
        context_capability=ContextAssemblyCapability(
            assembler=context_assembler,
            provider="custom",
            model_name="test-model",
            pricing_snapshot=None,
        ),
    )

    assert result.result.content == '{"ok": true}'
    assert captured["phase"] == "json_repair"
    assert captured["context_prepared"] is True
    assert "context_assembler" not in captured
