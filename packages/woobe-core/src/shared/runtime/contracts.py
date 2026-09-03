from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


class RunKind(StrEnum):
    AGENT = "agent"
    NETWORK = "network"


class RunStatus(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"
    UNCERTAIN = "uncertain"


TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.COMPLETED.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
        RunStatus.TIMED_OUT.value,
        RunStatus.UNCERTAIN.value,
    }
)


@dataclass(frozen=True, slots=True)
class RunReference:
    run_id: UUID
    kind: RunKind

    @classmethod
    def agent(cls, run_id: UUID) -> RunReference:
        return cls(run_id=run_id, kind=RunKind.AGENT)

    @classmethod
    def network(cls, run_id: UUID) -> RunReference:
        return cls(run_id=run_id, kind=RunKind.NETWORK)


@dataclass(frozen=True, slots=True)
class RuntimeFrame:
    event_type: str
    data: dict[str, Any]
    sequence: int | None = None


@runtime_checkable
class RuntimeLiveEvent(Protocol):
    event_type: str
    payload: dict[str, Any]


@runtime_checkable
class RuntimeLiveSource(Protocol):
    def subscribe(self) -> asyncio.Queue[RuntimeLiveEvent]: ...

    def unsubscribe(self, queue: asyncio.Queue[RuntimeLiveEvent]) -> None: ...
