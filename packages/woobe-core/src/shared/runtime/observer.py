from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
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
from shared.runtime.projection import (
    TERMINAL_RUNTIME_STATUSES,
    initial_projection,
    public_event,
    reduce_projection,
)
from shared.runtime.sse import format_sse_frame

logger = logging.getLogger(__name__)

DisconnectCheck = Callable[[], Awaitable[bool]]
DurableFallback = Callable[[], Awaitable[dict[str, Any] | None]]
RunIdResolver = Callable[[], UUID | None]
SourceDone = Callable[[], bool]
EarlyErrorFrame = Callable[[], RuntimeFrame | None]
HeartbeatData = Callable[[], dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _frame_size(frame: RuntimeFrame) -> int:
    return len(format_sse_frame(frame).encode("utf-8"))


class RuntimeStreamGapError(RuntimeError):
    """Raised when retained hot events cannot bridge the saved projection."""


class RuntimeStreamReader:
    """Resolve current Run state then follow the lossless live event tail."""

    def __init__(
        self,
        store: ExecutionStateStore,
        *,
        heartbeat_seconds: float = 15.0,
        block_ms: int = 1000,
        maxlen: int = 2000,
    ) -> None:
        self._store = store
        self._heartbeat_seconds = max(1.0, heartbeat_seconds)
        self._block_ms = max(50, block_ms)
        self._maxlen = max(100, maxlen)

    async def current_state(
        self,
        run_id: UUID,
        run_kind: str,
        *,
        durable_fallback: DurableFallback,
    ) -> tuple[dict[str, Any], str | None]:
        started = time.perf_counter()
        try:
            hot = await self._store.get(run_id)
        except Exception as exc:
            logger.warning("Runtime state unavailable for run_id=%s: %s", run_id, exc)
            hot = None

        if not hot:
            durable = await durable_fallback()
            if durable is None:
                raise KeyError(str(run_id))
            state = initial_projection(run_id, run_kind, durable)
            state.update(deepcopy(durable))
            state["run_id"] = str(run_id)
            state["kind"] = run_kind.upper()
            state["sequence"] = None
            state["realtime_available"] = False
            logger.info(
                "Runtime reattach state resolved",
                extra={
                    "run_id": str(run_id),
                    "run_kind": run_kind.upper(),
                    "realtime_available": False,
                    "high_watermark": None,
                    "projection_sequence": None,
                    "projection_lag": 0,
                    "catchup_events": 0,
                    "attach_latency_ms": round(
                        (time.perf_counter() - started) * 1000,
                        3,
                    ),
                },
            )
            return state, None

        try:
            reconnect_count = await self._store.increment(run_id, "reattach_count")
        except Exception:
            reconnect_count = None

        high_watermark = int(hot.get("event_sequence") or 0)
        high_cursor = hot.get("last_event_cursor")
        saved = hot.get("runtime_projection")
        projection = (
            deepcopy(saved)
            if isinstance(saved, dict)
            else initial_projection(run_id, run_kind, hot)
        )
        projection_sequence = int(projection.get("sequence") or 0)
        projection_lag = max(0, high_watermark - projection_sequence)
        catchup_events = 0

        if projection_sequence < high_watermark:
            first_sequence = await self._store.first_event_sequence(run_id)
            if (
                first_sequence is not None
                and first_sequence > projection_sequence + 1
            ):
                logger.warning(
                    "Runtime reattach projection gap",
                    extra={
                        "run_id": str(run_id),
                        "run_kind": run_kind.upper(),
                        "projection_sequence": projection_sequence,
                        "first_retained_sequence": first_sequence,
                        "high_watermark": high_watermark,
                        "projection_lag": projection_lag,
                    },
                )
                raise RuntimeStreamGapError(
                    "Runtime event history was trimmed before projection catch-up "
                    f"run_id={run_id} projection={projection_sequence} "
                    f"first={first_sequence}"
                )

            events = await self._store.list_events_after(
                run_id,
                projection_sequence,
                through_sequence=high_watermark,
                limit=max(self._maxlen, high_watermark - projection_sequence + 1),
            )
            if not events or events[-1].sequence != high_watermark:
                raise RuntimeStreamGapError(
                    f"Runtime projection cannot reach high-watermark run_id={run_id} "
                    f"projection={projection_sequence} high_watermark={high_watermark}"
                )

            catchup_events = len(events)
            expected = projection_sequence + 1
            for event in events:
                if event.sequence != expected:
                    raise RuntimeStreamGapError(
                        f"Runtime projection sequence gap run_id={run_id} "
                        f"expected={expected} observed={event.sequence}"
                    )
                public_type, public_payload = public_event(event)
                projection = reduce_projection(
                    projection,
                    public_type,
                    public_payload,
                    sequence=event.sequence,
                    occurred_at=event.occurred_at,
                )
                expected += 1
            if high_cursor is None:
                high_cursor = events[-1].cursor

        projection["sequence"] = high_watermark
        projection["run_id"] = str(run_id)
        projection["kind"] = run_kind.upper()
        projection["realtime_available"] = True
        logger.info(
            "Runtime reattach state resolved",
            extra={
                "run_id": str(run_id),
                "run_kind": run_kind.upper(),
                "realtime_available": True,
                "high_watermark": high_watermark,
                "projection_sequence": projection_sequence,
                "projection_lag": projection_lag,
                "catchup_events": catchup_events,
                "reattach_count": reconnect_count,
                "attach_latency_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return projection, str(high_cursor) if high_cursor is not None else None

    async def stream(
        self,
        run_id: UUID,
        run_kind: str,
        *,
        durable_fallback: DurableFallback,
    ) -> AsyncIterator[RuntimeFrame]:
        started = time.perf_counter()
        frame_count = 0
        live_event_count = 0
        approx_stream_bytes = 0
        final_status = "observer_closed"
        try:
            projection, cursor = await self.current_state(
                run_id,
                run_kind,
                durable_fallback=durable_fallback,
            )
            raw_sequence = projection.get("sequence")
            state_sequence = (
                raw_sequence
                if isinstance(raw_sequence, int) and not isinstance(raw_sequence, bool)
                else None
            )
            sequence = state_sequence or 0
            state_frame = RuntimeFrame(
                "run.state",
                projection,
                sequence=state_sequence,
            )
            frame_count += 1
            approx_stream_bytes += _frame_size(state_frame)
            yield state_frame

            status = str(projection.get("status") or "").lower()
            if status in TERMINAL_RUNTIME_STATUSES:
                final_status = status
                return
            if cursor is None:
                final_status = "realtime_unavailable"
                return

            last_heartbeat = time.monotonic()
            while True:
                try:
                    events = await self._store.read_events_after_cursor(
                        run_id,
                        cursor,
                        block_ms=self._block_ms,
                        limit=100,
                    )
                except Exception as exc:
                    logger.warning(
                        "Runtime live tail unavailable run_id=%s: %s",
                        run_id,
                        exc,
                    )
                    unavailable_frame = RuntimeFrame(
                        "run.realtime_unavailable",
                        {"run_id": str(run_id)},
                    )
                    frame_count += 1
                    approx_stream_bytes += _frame_size(unavailable_frame)
                    yield unavailable_frame
                    final_status = "realtime_unavailable"
                    return

                if not events:
                    now = time.monotonic()
                    if now - last_heartbeat >= self._heartbeat_seconds:
                        last_heartbeat = now
                        heartbeat = RuntimeFrame(
                            "heartbeat",
                            {"run_id": str(run_id), "ts": _now_iso()},
                        )
                        frame_count += 1
                        approx_stream_bytes += _frame_size(heartbeat)
                        yield heartbeat
                    continue

                for event in events:
                    cursor = event.cursor
                    if event.sequence <= sequence:
                        continue
                    expected = sequence + 1
                    if event.sequence != expected:
                        logger.warning(
                            "Runtime live tail sequence gap",
                            extra={
                                "run_id": str(run_id),
                                "run_kind": run_kind.upper(),
                                "expected_sequence": expected,
                                "observed_sequence": event.sequence,
                            },
                        )
                        raise RuntimeStreamGapError(
                            f"Runtime live tail sequence gap run_id={run_id} "
                            f"expected={expected} observed={event.sequence}"
                        )
                    public_type, public_payload = public_event(event)
                    projection = reduce_projection(
                        projection,
                        public_type,
                        public_payload,
                        sequence=event.sequence,
                        occurred_at=event.occurred_at,
                    )
                    sequence = event.sequence
                    frame = RuntimeFrame(
                        public_type,
                        {
                            "run_id": str(run_id),
                            "sequence": event.sequence,
                            "occurred_at": event.occurred_at,
                            **public_payload,
                        },
                        sequence=event.sequence,
                    )
                    frame_count += 1
                    live_event_count += 1
                    approx_stream_bytes += _frame_size(frame)
                    yield frame
                    status = str(projection.get("status") or "").lower()
                    if status in TERMINAL_RUNTIME_STATUSES:
                        final_status = status
                        return
        finally:
            logger.info(
                "Runtime reattach stream closed",
                extra={
                    "run_id": str(run_id),
                    "run_kind": run_kind.upper(),
                    "stream_status": final_status,
                    "stream_frames": frame_count,
                    "live_events": live_event_count,
                    "approx_stream_bytes": approx_stream_bytes,
                    "stream_duration_ms": round(
                        (time.perf_counter() - started) * 1000,
                        3,
                    ),
                },
            )


class RuntimeLocalSubscription:
    """One local observer subscription detached from execution ownership."""

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
        self._store = store
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
        hot_probe_failed = False
        try:
            hot = await self._store.get(run.run_id)
        except Exception:
            hot = None
            hot_probe_failed = True

        if hot is None and not hot_probe_failed:
            state, cursor = await self.current_state(
                run,
                durable_fallback=durable_fallback,
            )
            status = str(state.get("status") or "").lower()
            if cursor is None and status not in TERMINAL_RUNTIME_STATUSES:
                yield RuntimeFrame("run.state", dict(state), sequence=None)

                while True:
                    if disconnect_check is not None and await disconnect_check():
                        return
                    await asyncio.sleep(self._local_poll_seconds)

                    try:
                        hot = await self._store.get(run.run_id)
                    except Exception:
                        yield RuntimeFrame(
                            "run.realtime_unavailable",
                            {"run_id": str(run.run_id)},
                        )
                        return
                    if hot is not None:
                        break

                    durable = await durable_fallback()
                    if durable is None:
                        return
                    durable_status = str(durable.get("status") or "").lower()
                    if durable_status in TERMINAL_RUNTIME_STATUSES:
                        terminal_state, _ = await self.current_state(
                            run,
                            durable_fallback=durable_fallback,
                        )
                        yield RuntimeFrame(
                            "run.state",
                            dict(terminal_state),
                            sequence=None,
                        )
                        return

        async for frame in self._reader.stream(
            run.run_id,
            run.kind.value,
            durable_fallback=durable_fallback,
        ):
            if disconnect_check is not None and await disconnect_check():
                return
            yield frame

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
    "DurableFallback",
    "RuntimeLocalSubscription",
    "RuntimeObserver",
    "RuntimeStreamGapError",
    "RuntimeStreamReader",
]
