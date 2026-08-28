from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.infra.execution import tool_execution_loop


@pytest.mark.asyncio
async def test_bound_capabilities_without_calls_complete_in_one_model_invocation(monkeypatch) -> None:
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
        final_model=object(),
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
        final_model=object(),
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
async def test_repeated_semantic_failures_go_to_terminal_recovery(monkeypatch) -> None:
    phases: list[str] = []
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
        model=object(),
        final_model=object(),
        execute_single_tool=lambda *_args, **_kwargs: None,
        messages=[HumanMessage(content="Find the repository")],
        tool_name_to_id={"lookup": "lookup"},
        provider="custom",
        model_name="test-model",
        initial_phase="capability_response_generation",
        final_json_instruction=None,
    )

    assert phases == [
        "capability_response_generation",
        "tool_followup_1",
        "final_response_generation",
    ]
    assert len(execution.tool_calls) == 2
    assert execution.result.content == "Need the exact identifier."
