from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import Field

from modules.agent.application.strategy_sdk import ExecutionState
from modules.agent.infra.execution.strategies.standard import (
    StandardExecutionState,
    StandardStopReason,
)
from modules.agent.infra.execution.strategy_runtime.state import RuntimeStrategyStateStore


class _Mode(StrEnum):
    READY = "ready"


class _NestedState(ExecutionState):
    mode: _Mode = _Mode.READY
    step: int = 0
    values: list[dict[str, int]] = Field(default_factory=list)


def test_strategy_state_store_round_trips_typed_state() -> None:
    store = RuntimeStrategyStateStore()
    state = _NestedState(step=2, values=[{"value": 7}])

    payload = store.dump(state)
    restored = store.create(
        _NestedState,
        {"state": payload},
        strategy_name="test",
    )

    assert payload == {
        "mode": "ready",
        "step": 2,
        "values": [{"value": 7}],
    }
    assert restored == state
    assert restored.mode is _Mode.READY


def test_strategy_state_store_creates_fresh_default_state_without_checkpoint() -> None:
    store = RuntimeStrategyStateStore()

    state = store.create(_NestedState, None, strategy_name="test")

    assert state == _NestedState()


def test_strategy_state_store_rejects_generic_checkpoint_without_state_payload() -> None:
    store = RuntimeStrategyStateStore()

    with pytest.raises(RuntimeError, match="missing state"):
        store.create(
            _NestedState,
            {"iteration": 2},
            strategy_name="test",
        )


def test_strategy_state_store_restores_legacy_standard_cursor() -> None:
    store = RuntimeStrategyStateStore()

    state = store.create(
        StandardExecutionState,
        {
            "next_phase": "final_response_generation",
            "round_index": 5,
            "consecutive_failure_rounds": 2,
            "stopped_reason": "capability round limit reached",
            "next_call_index": 3,
        },
        strategy_name="standard",
    )

    assert state.phase == "final_response_generation"
    assert state.tool_round == 5
    assert state.consecutive_failures == 2
    assert state.stop_reason is StandardStopReason.CAPABILITY_ROUND_LIMIT
