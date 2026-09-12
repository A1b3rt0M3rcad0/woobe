from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from shared.contracts.run_event_buffer import RunEventAppendReceipt, RunEventBufferPort
from shared.runtime.durability import RunDurabilityBarrier
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


@dataclass
class DurableRunEventRecorder:
    """Run-scoped canonical event recorder separated from best-effort SSE projection."""

    buffer: RunEventBufferPort
    barrier: RunDurabilityBarrier
    run_id: UUID
    run_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)
    storage_version: str = EVENT_JOURNAL_STORAGE_VERSION
    attempt: int = 1

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        durable: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> RunEventAppendReceipt:
        merged_metadata = {
            **self.metadata,
            "attempt": self.attempt,
            **(metadata or {}),
        }
        receipt = await self.buffer.append(
            run_id=self.run_id,
            run_kind=self.run_kind,
            event_type=event_type,
            payload=payload or {},
            metadata=merged_metadata,
            storage_version=self.storage_version,
        )
        if durable:
            await self.barrier.wait_until(self.run_id, receipt.sequence)
        return receipt

    async def checkpoint(
        self,
        state: dict[str, Any],
        *,
        durable: bool = True,
    ) -> RunEventAppendReceipt:
        return await self.emit(
            "execution.checkpoint",
            {"attempt": self.attempt, "state": state},
            durable=durable,
        )


current_run_event_recorder: ContextVar[DurableRunEventRecorder | None] = ContextVar(
    "current_run_event_recorder",
    default=None,
)


def bind_run_event_recorder(recorder: DurableRunEventRecorder | None) -> Token:
    return current_run_event_recorder.set(recorder)


def reset_run_event_recorder(token: Token) -> None:
    current_run_event_recorder.reset(token)
