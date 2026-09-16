from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Mapping, Protocol, TypeVar

from modules.agent.application.interfaces.execution import InstrumentedExecution


StateT = TypeVar("StateT")


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


class StrategyStateFactory(Protocol, Generic[StateT]):
    def create(
        self,
        initialization: StrategyInitialization,
        resume: StrategyResumeSnapshot | None,
    ) -> StateT: ...


class StrategyStateCodec(Protocol, Generic[StateT]):
    def dump_cursor(self, state: StateT) -> dict[str, Any]: ...

    def checkpoint_phase(self, state: StateT) -> str: ...

    def messages(self, state: StateT) -> list[Any]: ...
