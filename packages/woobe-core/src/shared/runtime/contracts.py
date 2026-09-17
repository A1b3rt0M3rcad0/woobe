from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4


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


RUNTIME_STREAM_PROTOCOL_VERSION = 2
RUNTIME_CONTROL_EVENT_TYPES = frozenset(
    {
        "heartbeat",
        "run.realtime_unavailable",
        "error",
        "protocol.control",
    }
)


@dataclass(frozen=True, slots=True)
class RuntimeFrame:
    event_type: str
    data: dict[str, Any]
    sequence: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticRuntimeEvent(RuntimeFrame):
    run_id: UUID
    session_id: UUID
    run_kind: RunKind
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.run_id or not self.session_id or not self.event_id or not self.occurred_at:
            raise ValueError("Semantic runtime event requires Run and Session identity")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("Semantic runtime event requires a nonnegative sequence")
        if self.event_type in RUNTIME_CONTROL_EVENT_TYPES - {"error"}:
            raise ValueError("Transport frames cannot be semantic events")


@dataclass(frozen=True, slots=True)
class RuntimeControlFrame(RuntimeFrame):
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.sequence is not None:
            raise ValueError("Transport frames cannot advance semantic ordering")
        if self.event_type not in RUNTIME_CONTROL_EVENT_TYPES:
            raise ValueError(f"Unsupported runtime control frame: {self.event_type}")


def runtime_state_frame(state: dict[str, Any]) -> SemanticRuntimeEvent:
    """A fresh observation at the public-stream watermark, never journal sequence."""
    return SemanticRuntimeEvent(
        event_type="run.state", data=dict(state),
        sequence=int(state.get("sequence") or 0),
        run_id=UUID(str(state["run_id"])),
        session_id=UUID(str(state.get("session_id") or state["network_session_id"])),
        run_kind=RunKind(str(state["kind"]).lower()),
    )


@runtime_checkable
class RuntimeLiveEvent(Protocol):
    event_type: str
    payload: dict[str, Any]


@runtime_checkable
class RuntimeLiveSource(Protocol):
    def subscribe(self) -> asyncio.Queue[Any]: ...

    def unsubscribe(self, queue: asyncio.Queue[Any]) -> None: ...
