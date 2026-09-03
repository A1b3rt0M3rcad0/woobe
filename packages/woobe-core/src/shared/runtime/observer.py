from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.contracts.execution_state import ExecutionStateStore
from shared.runtime.contracts import (
    RunKind,
    RunReference,
    RuntimeFrame,
    RuntimeLiveEvent,
    RuntimeLiveSource,
)
from shared.runtime_reattach import (
    DurableFallback,
    RuntimeStreamGapError,
    RuntimeStreamReader,
)

DisconnectCheck = Callable[[], Awaitable[bool]]
RunIdResolver = Callable[[], UUID | None]
SourceDone = Callable[[], bool]
EarlyErrorFrame = Callable[[], RuntimeFrame | None]
HeartbeatData = Callable[[], dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeLocalSubscription:
    """One local observer subscription detached from execution ownership.

    The subscription owns only its queue. Closing it never cancels the execution
    or removes the canonical hot Run state.
    """

    def __init__(
        self,
        source: RuntimeLiveSource,
        *,
        heartbeat_seconds: float,
        poll_seconds: float,
        run_id_resolver: RunIdResolver | None = None,
        heartbeat_data: HeartbeatData | None = None,
    ) -> None:
        self._source = source
        self._queue = source.subscribe()
        self._heartbeat_seconds = max(1.0, heartbeat_seconds)
        self._poll_seconds = max(0.01, poll_seconds)
        self._run_id_resolver = run_id_resolver
        self._heartbeat_data = heartbeat_data
        self._closed = False

    def _resolved_run_id(self) -> UUID | None:
        return self._run_id_resolver() if self._run_id_resolver is not None else None

    def _frame(self, event: RuntimeLiveEvent) -> RuntimeFrame:
        payload = dict(event.payload)
        run_id = self._resolved_run_id()
        if run_id is not None and payload.get("run_id") is None:
            payload["run_id"] = str(run_id)
        return RuntimeFrame(event.event_type, payload, sequence=None)

    def _heartbeat_frame(self) -> RuntimeFrame:
        run_id = self._resolved_run_id()
        payload: dict[str, Any] = {
            "run_id": str(run_id) if run_id is not None else None,
            "ts": _now_iso(),
        }
        if self._heartbeat_data is not None:
            payload.update(self._heartbeat_data())
        return RuntimeFrame("heartbeat", payload)

    async def stream(
        self,
        *,
        disconnect_check: DisconnectCheck | None = None,
        source_done: SourceDone | None = None,
        early_error_frame: EarlyErrorFrame | None = None,
    ) -> AsyncIterator[RuntimeFrame]:
        last_heartbeat = time.monotonic()
        terminal_events = {"done", "error", "cancelled"}
        try:
            while True:
                if disconnect_check is not None and await disconnect_check():
                    return
                try:
                    event = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._poll_seconds,
                    )
                except asyncio.TimeoutError:
                    now = time.monotonic()
                    if now - last_heartbeat >= self._heartbeat_seconds:
                        last_heartbeat = now
                        yield self._heartbeat_frame()
                    if source_done is not None and source_done() and self._queue.empty():
                        if early_error_frame is not None:
                            frame = early_error_frame()
                            if frame is not None:
                                yield frame
                        return
                    continue

                last_heartbeat = time.monotonic()
                frame = self._frame(event)
                yield frame
                if event.event_type in terminal_events:
                    return
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._source.unsubscribe(self._queue)


class RuntimeObserver:
    """Canonical Run observation boundary.

    Hot reattach is projection + high-watermark catch-up + live tail. The initial
    Agent fast path can be observed through a local source without making Redis
    part of TTFT. Both paths emit the same RuntimeFrame language and neither owns
    execution lifecycle.
    """

    def __init__(
        self,
        store: ExecutionStateStore,
        *,
        heartbeat_seconds: float = 15.0,
        block_ms: int = 1000,
        maxlen: int = 2000,
        local_poll_seconds: float = 0.25,
    ) -> None:
        self._heartbeat_seconds = max(1.0, heartbeat_seconds)
        self._local_poll_seconds = max(0.01, local_poll_seconds)
        self._reader = RuntimeStreamReader(
            store,
            heartbeat_seconds=heartbeat_seconds,
            block_ms=block_ms,
            maxlen=maxlen,
        )

    async def current_state(
        self,
        run: RunReference,
        *,
        durable_fallback: DurableFallback,
    ) -> tuple[dict[str, Any], str | None]:
        return await self._reader.current_state(
            run.run_id,
            run.kind.value,
            durable_fallback=durable_fallback,
        )

    async def observe(
        self,
        run: RunReference,
        *,
        durable_fallback: DurableFallback,
        disconnect_check: DisconnectCheck | None = None,
    ) -> AsyncIterator[RuntimeFrame]:
        async for frame in self._reader.stream(
            run.run_id,
            run.kind.value,
            durable_fallback=durable_fallback,
        ):
            if disconnect_check is not None and await disconnect_check():
                return
            yield RuntimeFrame(
                event_type=frame.event_type,
                data=dict(frame.data),
                sequence=frame.sequence,
            )

    def subscribe_local(
        self,
        source: RuntimeLiveSource,
        *,
        run_kind: RunKind,
        run_id_resolver: RunIdResolver | None = None,
        heartbeat_data: HeartbeatData | None = None,
    ) -> RuntimeLocalSubscription:
        del run_kind
        return RuntimeLocalSubscription(
            source,
            heartbeat_seconds=self._heartbeat_seconds,
            poll_seconds=self._local_poll_seconds,
            run_id_resolver=run_id_resolver,
            heartbeat_data=heartbeat_data,
        )


__all__ = [
    "RuntimeLocalSubscription",
    "RuntimeObserver",
    "RuntimeStreamGapError",
]
