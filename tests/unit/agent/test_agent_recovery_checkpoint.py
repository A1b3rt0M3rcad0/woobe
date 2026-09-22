from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution.agent_recovery_checkpoint import (
    build_agent_checkpoint_state,
    checkpoint_agent_boundary,
    load_agent_execution_resume,
)
from modules.agent.infra.execution import tool_execution_loop


def _execution() -> InstrumentedExecution:
    return InstrumentedExecution(
        result=None,
        tool_calls=[
            ToolCallInfo(
                tool_call_id="call-1",
                tool_name="lookup",
                input={"id": "123"},
                output={"customer": "active"},
                duration_ms=12,
            )
        ],
        llm_calls=[
            {
                "call_id": "model-1",
                "call_index": 1,
                "phase": "capability_response_generation",
                "status": "success",
                "occurred_at": "2026-09-10T20:00:00+00:00",
            }
        ],
        timeline=[
            {
                "kind": "tool",
                "occurred_at": "2026-09-10T20:00:01+00:00",
                "payload": {"tool_call_id": "call-1"},
            }
        ],
        tool_wall_latency_ms=15,
        tool_call_duration_sum_ms=12,
    )


def _checkpoint_state() -> dict:
    base = [HumanMessage(content="original request")]
    continuation = [
        AIMessage(
            content="",
            tool_calls=[{"id": "call-1", "name": "lookup", "args": {"id": "123"}}],
            additional_kwargs={"reasoning_content": "private reasoning"},
        ),
        ToolMessage(content='{"customer":"active"}', tool_call_id="call-1"),
    ]
    return build_agent_checkpoint_state(
        phase="agent_tool_boundary",
        tool_loop_messages=[*base, *continuation],
        base_message_count=len(base),
        execution=_execution(),
        next_phase="tool_followup_1",
        next_call_index=2,
        round_index=1,
        consecutive_failure_rounds=0,
    )


def test_checkpoint_round_trip_keeps_only_capability_continuation() -> None:
    state = _checkpoint_state()

    assert state["phase"] == "agent_tool_boundary"
    assert state["resume_policy"] == "continue_after_durable_tool_results"
    assert [item["role"] for item in state["capability_messages"]] == [
        "assistant",
        "tool",
    ]
    assert "original request" not in str(state["capability_messages"])

    resume = load_agent_execution_resume(state)
    assert resume is not None
    assert resume.next_phase == "tool_followup_1"
    assert resume.next_call_index == 2
    assert resume.round_index == 1
    assert len(resume.execution.tool_calls) == 1
    assert len(resume.execution.llm_calls) == 1
    assert isinstance(resume.capability_messages[0], AIMessage)
    assert (
        resume.capability_messages[0].additional_kwargs["reasoning_content"]
        == "private reasoning"
    )
    assert isinstance(resume.capability_messages[1], ToolMessage)


@pytest.mark.asyncio
async def test_checkpoint_is_durable_when_run_recorder_is_bound() -> None:
    recorded = {}

    class Recorder:
        async def checkpoint(self, state, *, durable=True):
            recorded["state"] = state
            recorded["durable"] = durable

    context = new_execution_context()
    context.run_event_recorder = Recorder()
    token = current_execution.set(context)
    try:
        await checkpoint_agent_boundary(
            phase="agent_tool_boundary",
            tool_loop_messages=[
                HumanMessage(content="base"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call-1", "name": "lookup", "args": {}}],
                ),
                ToolMessage(content="ok", tool_call_id="call-1"),
            ],
            base_message_count=1,
            execution=_execution(),
            next_phase="tool_followup_1",
            next_call_index=2,
            round_index=1,
            consecutive_failure_rounds=0,
        )
    finally:
        current_execution.reset(token)

    assert recorded["durable"] is True
    assert recorded["state"]["next_phase"] == "tool_followup_1"


@pytest.mark.asyncio
async def test_tool_loop_resumes_after_durable_tool_boundary_without_repeating_tool(
    monkeypatch,
) -> None:
    calls = []

    async def fake_invoke_llm(**kwargs):
        calls.append(kwargs)
        return (
            SimpleNamespace(content="recovered answer", tool_calls=[]),
            {
                "call_id": "model-2",
                "call_index": kwargs["call_index"],
                "phase": kwargs["phase"],
                "status": "success",
                "occurred_at": "2026-09-10T20:00:02+00:00",
            },
        )

    async def must_not_execute_tool(_call, _tool_id):
        raise AssertionError("durably completed Tool must not be replayed")

    monkeypatch.setattr(tool_execution_loop, "invoke_llm", fake_invoke_llm)
    context = new_execution_context()
    context.resume_state = _checkpoint_state()
    token = current_execution.set(context)
    try:
        execution, call_index = await tool_execution_loop.run_tool_loop(
            model=object(),
            execute_single_tool=must_not_execute_tool,
            messages=[HumanMessage(content="original request")],
            tool_name_to_id={"lookup": "tool-1"},
            provider="custom",
            model_name="model",
            initial_phase="capability_response_generation",
            final_json_instruction=None,
        )
    finally:
        current_execution.reset(token)

    assert call_index == 2
    assert len(calls) == 1
    assert calls[0]["phase"] == "tool_followup_1"
    assert calls[0]["call_index"] == 2
    assert len(execution.tool_calls) == 1
    assert len(execution.llm_calls) == 2
    assert execution.result.content == "recovered answer"
    assert context.resume_state is None
