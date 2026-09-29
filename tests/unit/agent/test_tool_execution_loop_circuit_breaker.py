from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.infra.execution import tool_execution_loop


def _unexpected_recovery_model():
    raise AssertionError("Recovery model must not be created on the normal path")


@pytest.mark.asyncio
async def test_bound_capabilities_without_calls_complete_in_one_model_invocation(
    monkeypatch,
) -> None:
    phases: list[str] = []

    async def fake_invoke_llm(**kwargs):
        phases.append(kwargs["phase"])
        return SimpleNamespace(content="Direct answer", tool_calls=[]), {
            "phase": kwargs["phase"],
            "occurred_at": "2026-07-16T12:00:00+00:00",
            "status": "success",
        }

    monkeypatch.setattr(tool_execution_loop, "invoke_llm", fake_invoke_llm)

    execution, _ = await tool_execution_loop.run_tool_loop(
        model=object(),
        final_model_factory=_unexpected_recovery_model,
        execute_single_tool=lambda *_args, **_kwargs: None,
        messages=[HumanMessage(content="Explain what you can do")],
        tool_name_to_id={"lookup": "lookup"},
        provider="custom",
        model_name="test-model",
        initial_phase="capability_response_generation",
        final_json_instruction=None,
    )

    assert phases == ["capability_response_generation"]
    assert execution.tool_calls == []
    assert execution.result.content == "Direct answer"


@pytest.mark.asyncio
async def test_initial_tool_call_is_executed_by_standard_strategy(monkeypatch) -> None:
    order: list[str] = []

    async def fake_invoke_llm(**kwargs):
        order.append("model")
        return SimpleNamespace(content="done", tool_calls=[]), {
            "call_id": "model-1",
            "call_index": kwargs["call_index"],
            "phase": kwargs["phase"],
            "occurred_at": "2026-09-26T18:00:00+00:00",
            "status": "success",
        }

    async def fake_execute_tool_call(*, tool_call, **_kwargs):
        order.append("tool")
        info = ToolCallInfo(
            tool_call_id=tool_call["id"],
            tool_name=tool_call["name"],
            input=tool_call["args"],
            output={"success": True},
            success=True,
            status="success",
        )
        return (
            info,
            ToolMessage(content="ok", tool_call_id=tool_call["id"]),
            {
                "occurred_at": "2026-09-26T18:00:00+00:00",
                "success": True,
            },
        )

    monkeypatch.setattr(tool_execution_loop, "invoke_llm", fake_invoke_llm)
    monkeypatch.setattr(tool_execution_loop, "execute_tool_call", fake_execute_tool_call)

    execution, _ = await tool_execution_loop.run_tool_loop(
        model=object(),
        execute_single_tool=lambda *_args, **_kwargs: None,
        messages=[HumanMessage(content="continue")],
        tool_name_to_id={"bootstrap_lookup": "tool-id"},
        provider="custom",
        model_name="test-model",
        initial_phase="capability_response_generation",
        final_json_instruction=None,
        initial_tool_call={
            "id": "bootstrap-1",
            "name": "bootstrap_lookup",
            "args": {"id": "123"},
        },
    )

    assert order == ["tool", "model"]
    assert len(execution.tool_calls) == 1
    assert execution.tool_calls[0].tool_call_id == "bootstrap-1"
    assert execution.result.content == "done"


@pytest.mark.asyncio
async def test_one_capability_call_needs_only_one_followup_invocation(monkeypatch) -> None:
    phases: list[str] = []
    planned_results = [
        SimpleNamespace(
            content="",
            tool_calls=[{"id": "tool-1", "name": "lookup", "args": {"id": "123"}}],
        ),
        SimpleNamespace(content="Customer 123 is active.", tool_calls=[]),
    ]

    async def fake_invoke_llm(**kwargs):
        phases.append(kwargs["phase"])
        result = planned_results[len(phases) - 1]
        return result, {
            "phase": kwargs["phase"],
            "occurred_at": "2026-07-16T12:00:00+00:00",
            "status": "success",
        }

    async def fake_execute_tool_call(*, tool_call, **_kwargs):
        info = ToolCallInfo(
            tool_call_id=tool_call["id"],
            tool_name=tool_call["name"],
            input=tool_call["args"],
            output={"success": True, "result": {"active": True}},
            success=True,
            status="success",
        )
        message = ToolMessage(content='{"active": true}', tool_call_id=tool_call["id"])
        payload = {
            "occurred_at": "2026-07-16T12:00:00+00:00",
            "success": True,
        }
        return info, message, payload

    monkeypatch.setattr(tool_execution_loop, "invoke_llm", fake_invoke_llm)
    monkeypatch.setattr(tool_execution_loop, "execute_tool_call", fake_execute_tool_call)

    execution, _ = await tool_execution_loop.run_tool_loop(
        model=object(),
        final_model_factory=_unexpected_recovery_model,
        execute_single_tool=lambda *_args, **_kwargs: None,
        messages=[HumanMessage(content="Check customer 123")],
        tool_name_to_id={"lookup": "lookup"},
        provider="custom",
        model_name="test-model",
        initial_phase="capability_response_generation",
        final_json_instruction=None,
    )

    assert phases == ["capability_response_generation", "tool_followup_1"]
    assert len(execution.tool_calls) == 1
    assert execution.result.content == "Customer 123 is active."


@pytest.mark.asyncio
async def test_repeated_semantic_failures_create_terminal_recovery_lazily(
    monkeypatch,
) -> None:
    phases: list[str] = []
    invoked_models: list[object] = []
    primary_model = object()
    recovery_model = object()
    recovery_create_count = 0
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

    def create_recovery_model():
        nonlocal recovery_create_count
        recovery_create_count += 1
        return recovery_model

    async def fake_invoke_llm(**kwargs):
        phases.append(kwargs["phase"])
        invoked_models.append(kwargs["model"])
        result = planned_results[len(phases) - 1]
        return result, {
            "phase": kwargs["phase"],
            "occurred_at": "2026-07-16T12:00:00+00:00",
            "status": "success",
        }

    async def fake_execute_tool_call(*, tool_call, **_kwargs):
        info = ToolCallInfo(
            tool_call_id=tool_call["id"],
            tool_name=tool_call["name"],
            input=tool_call["args"],
            output={"success": True, "result": "Repository not found"},
            success=False,
            status="error",
            error_code="repository_not_found",
            error="Repository not found",
        )
        message = ToolMessage(content="failed", tool_call_id=tool_call["id"])
        payload = {
            "occurred_at": "2026-07-16T12:00:00+00:00",
            "success": False,
        }
        return info, message, payload

    monkeypatch.setattr(tool_execution_loop, "invoke_llm", fake_invoke_llm)
    monkeypatch.setattr(tool_execution_loop, "execute_tool_call", fake_execute_tool_call)

    execution, _ = await tool_execution_loop.run_tool_loop(
        model=primary_model,
        final_model_factory=create_recovery_model,
        execute_single_tool=lambda *_args, **_kwargs: None,
        messages=[HumanMessage(content="Find the repository")],
        tool_name_to_id={"lookup": "lookup"},
        provider="custom",
        model_name="test-model",
        initial_phase="capability_response_generation",
        final_json_instruction=None,
    )

    assert recovery_create_count == 1
    assert phases == [
        "capability_response_generation",
        "tool_followup_1",
        "final_response_generation",
    ]
    assert invoked_models == [primary_model, primary_model, recovery_model]
    assert len(execution.tool_calls) == 2
    assert execution.result.content == "Need the exact identifier."
