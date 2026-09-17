from __future__ import annotations

from enum import StrEnum
from typing import Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ExecutionCheckpointBoundary(StrEnum):
    """Shared durable boundaries that any Execution Strategy may checkpoint at."""

    PREFLIGHT = "agent_preflight_boundary"
    TOOL = "agent_tool_boundary"


class ExecutionPhase(StrEnum):
    """Base enum for Strategy-specific execution phases."""


class ExecutionStopReason(StrEnum):
    """Base enum for Strategy-specific stop reasons."""


class ExecutionState(BaseModel):
    """Serializable algorithm state owned by one concrete Execution Strategy."""

    model_config = ConfigDict(extra="forbid")


StateT = TypeVar("StateT", bound=ExecutionState)


@runtime_checkable
class ExecutionPolicy(Protocol, Generic[StateT]):
    """Optional stop policy specialized by one concrete Execution Strategy."""

    def stop_reason(self, state: StateT) -> ExecutionStopReason | None: ...
