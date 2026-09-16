from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Mapping, Protocol, Self, TypeVar, runtime_checkable

from modules.agent.application.interfaces.execution import InstrumentedExecution


StateT = TypeVar("StateT")


class ExecutionCheckpointBoundary(StrEnum):
    """Shared durable boundaries that any Execution Strategy may checkpoint at."""

    PREFLIGHT = "agent_preflight_boundary"
    TOOL = "agent_tool_boundary"


class StrategyDecisionType(StrEnum):
    CONTINUE = "continue"
    FINALIZE = "finalize"


@runtime_checkable
class ExecutionStopReason(Protocol):
    """Shared shape for Strategy-specific stop-reason enums."""

    @property
    def value(self) -> str: ...


StopReasonLike = str | ExecutionStopReason


def stop_reason_value(reason: StopReasonLike | None) -> str | None:
    if reason is None or isinstance(reason, str):
        return reason
    return reason.value


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    type: StrategyDecisionType
    reason: StopReasonLike | None = None


@dataclass(frozen=True, slots=True)
class StrategyInitialization:
    messages: tuple[Any, ...]
    initial_phase: str
    bootstrap: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategyResumeSnapshot:
    phase: str
    cursor: Mapping[str, Any]
    capability_messages: tuple[Any, ...]
    execution: InstrumentedExecution


@runtime_checkable
class ExecutionState(Protocol):
    """State contract implemented inside each concrete Strategy file."""

    messages: list[Any]

    @classmethod
    def create(
        cls,
        initialization: StrategyInitialization,
        resume: StrategyResumeSnapshot | None,
    ) -> Self: ...

    def checkpoint_cursor(self) -> dict[str, Any]: ...

    def checkpoint_messages(self) -> list[Any]: ...


@runtime_checkable
class ExecutionPolicy(Protocol, Generic[StateT]):
    """Policy contract specialized by each Execution Strategy."""

    def evaluate(self, state: StateT) -> StrategyDecision: ...
