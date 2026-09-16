from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    StrategyInitialization,
    StrategyModelResult,
    StrategyResumeSnapshot,
    StrategyToolBatch,
)
from modules.agent.infra.execution.strategies.standard.phases import (
    StandardCheckpointBoundary,
    StandardPhase,
    is_standard_model_phase,
)


@dataclass(slots=True)
class StandardExecutionState:
    messages: list[Any]
    next_phase: str
    tool_round: int = 0
    consecutive_failures: int = 0
    stopped_reason: str | None = None
    checkpoint_boundary: StandardCheckpointBoundary = StandardCheckpointBoundary.TOOL
    initial_tool_call: dict[str, Any] | None = None

    def record_model_result(self, result: StrategyModelResult) -> None:
        if result.has_tool_calls:
            self.messages.append(result.message)

    def record_tool_batch(
        self,
        batch: StrategyToolBatch,
        *,
        count_round: bool = True,
    ) -> None:
        self.messages.extend(batch.messages)
        if count_round:
            self.tool_round += 1
            self.consecutive_failures = (
                self.consecutive_failures + 1 if batch.has_failures else 0
            )


class StandardStateFactory:
    def create(
        self,
        initialization: StrategyInitialization,
        resume: StrategyResumeSnapshot | None,
    ) -> StandardExecutionState:
        initial_tool_call = initialization.bootstrap.get("initial_tool_call")
        if initial_tool_call is not None and not isinstance(initial_tool_call, dict):
            raise ValueError("Standard initial_tool_call must be a mapping")

        if resume is None:
            if not is_standard_model_phase(initialization.initial_phase):
                raise ValueError(
                    f"Unsupported Standard initial phase: {initialization.initial_phase}"
                )
            return StandardExecutionState(
                messages=list(initialization.messages),
                next_phase=initialization.initial_phase,
                initial_tool_call=initial_tool_call,
            )

        cursor = dict(resume.cursor)
        next_phase = cursor.get("next_phase")
        if not isinstance(next_phase, str) or not is_standard_model_phase(next_phase):
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint is missing next execution phase",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            )
        try:
            tool_round = max(0, int(cursor.get("round_index") or 0))
            consecutive_failures = max(
                0,
                int(cursor.get("consecutive_failure_rounds") or 0),
            )
        except (TypeError, ValueError) as exc:
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint contains an invalid Standard cursor",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            ) from exc
        stopped_reason = (
            str(cursor["stopped_reason"])
            if cursor.get("stopped_reason")
            else None
        )
        if next_phase == StandardPhase.FINAL_RESPONSE_GENERATION.value and not stopped_reason:
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint is missing terminal stop reason",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            )
        return StandardExecutionState(
            messages=[*initialization.messages, *resume.capability_messages],
            next_phase=next_phase,
            tool_round=tool_round,
            consecutive_failures=consecutive_failures,
            stopped_reason=stopped_reason,
            initial_tool_call=None,
        )


class StandardStateCodec:
    def dump_cursor(self, state: StandardExecutionState) -> dict[str, Any]:
        return {
            "next_phase": state.next_phase,
            "round_index": state.tool_round,
            "consecutive_failure_rounds": state.consecutive_failures,
            "stopped_reason": state.stopped_reason,
        }

    def checkpoint_phase(self, state: StandardExecutionState) -> str:
        return state.checkpoint_boundary.value

    def messages(self, state: StandardExecutionState) -> list[Any]:
        return state.messages
