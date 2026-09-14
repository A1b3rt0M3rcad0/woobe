from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution.agent_recovery_checkpoint import (
    build_strategy_checkpoint_state,
    load_strategy_execution_resume,
)
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability


def _execution() -> InstrumentedExecution:
    execution = InstrumentedExecution(result=None)
    execution.llm_calls.append(
        {
            "call_id": "model-1",
            "call_index": 1,
            "phase": "reason_1",
            "occurred_at": "2026-09-14T18:00:00+00:00",
        }
    )
    return execution


def _messages() -> list:
    return [
        HumanMessage(content="base request"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call-1",
                    "name": "search",
                    "args": {"q": "woobe"},
                }
            ],
        ),
        ToolMessage(content="result", tool_call_id="call-1"),
    ]


def test_strategy_checkpoint_preserves_opaque_cursor() -> None:
    state = build_strategy_checkpoint_state(
        strategy_name="test_iterative",
        phase="iteration_boundary",
        messages=_messages(),
        base_message_count=1,
        execution=_execution(),
        cursor={
            "next_step": "reflect",
            "iteration": 3,
            "planner": {"remaining": 2},
        },
    )

    assert state["resume_policy"] == "continue_execution_strategy"
    assert state["execution_strategy"] == "test_iterative"
    assert state["phase"] == "iteration_boundary"
    assert [item["role"] for item in state["capability_messages"]] == [
        "assistant",
        "tool",
    ]

    resume = load_strategy_execution_resume(
        state,
        strategy_name="test_iterative",
    )

    assert resume is not None
    assert resume.strategy_name == "test_iterative"
    assert resume.phase == "iteration_boundary"
    assert resume.cursor == {
        "next_step": "reflect",
        "iteration": 3,
        "planner": {"remaining": 2},
    }
    assert len(resume.execution.llm_calls) == 1
    assert len(resume.capability_messages) == 2


def test_strategy_checkpoint_cannot_be_resumed_by_another_strategy() -> None:
    state = build_strategy_checkpoint_state(
        strategy_name="test_iterative",
        phase="iteration_boundary",
        messages=_messages(),
        base_message_count=1,
        execution=_execution(),
        cursor={"next_step": "reflect"},
    )

    assert (
        load_strategy_execution_resume(
            state,
            strategy_name="standard",
        )
        is None
    )


@pytest.mark.asyncio
async def test_recovery_capability_persists_and_rehydrates_strategy_cursor() -> None:
    recorded: dict = {}

    class Recorder:
        async def checkpoint(self, state, *, durable=True):
            recorded["state"] = state
            recorded["durable"] = durable

    context = new_execution_context()
    context.run_event_recorder = Recorder()
    token = current_execution.set(context)
    try:
        capability = StrategyRecoveryCapability(strategy_name="test_iterative")
        execution = _execution()
        await capability.checkpoint(
            phase="iteration_boundary",
            messages=_messages(),
            base_message_count=1,
            execution=execution,
            cursor={"next_step": "reflect", "iteration": 2},
        )

        assert recorded["durable"] is True
        context.resume_state = recorded["state"]
        resume = capability.load()

        assert resume is not None
        assert resume.cursor == {"next_step": "reflect", "iteration": 2}
        assert context.resume_state is None
        assert context.execution is not None
        assert context.execution is not execution
        assert context.execution.llm_calls == execution.llm_calls
    finally:
        current_execution.reset(token)


def test_generic_checkpoint_rejects_non_mapping_cursor() -> None:
    with pytest.raises(ValueError, match="cursor must be a mapping"):
        build_strategy_checkpoint_state(
            strategy_name="test_iterative",
            phase="iteration_boundary",
            messages=[SimpleNamespace(content="base")],
            base_message_count=1,
            execution=_execution(),
            cursor=[],  # type: ignore[arg-type]
        )
