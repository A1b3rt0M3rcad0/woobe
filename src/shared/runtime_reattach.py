from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.contracts.execution_state import ExecutionEvent, ExecutionStateStore

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_STRUCTURAL_EVENTS = {
    "agent.run.accepted",
    "execution_started",
    "agent_invocation_started",
    "agent_invocation_completed",
    "agent_invocation_failed",
    "delegation_started",
    "delegation_completed",
    "tool_call_started",
    "tool_call_completed",
    "usage",
    "done",
    "error",
    "cancelled",
    "execution_completed",
    "execution_failed",
    "execution_cancelled",
}


class RuntimeStreamGapError(RuntimeError):
    """Raised when the retained hot stream cannot bridge the saved projection."""


@dataclass(frozen=True)
class RuntimeStreamFrame:
    event_type: str
    data: dict[str, Any]
    sequence: int | None = None


def format_sse_frame(frame: RuntimeStreamFrame) -> str:
    prefix = f"id: {frame.sequence}\n" if frame.sequence is not None else ""
    payload = {"type": frame.event_type, **frame.data}
    return (
        f"{prefix}event: {frame.event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    )


def _frame_size(frame: RuntimeStreamFrame) -> int:
    return len(format_sse_frame(frame).encode("utf-8"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def initial_projection(
    run_id: UUID,
    run_kind: str,
    hot_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = hot_state or {}
    root_result = state.get("root_result")
    root_result = root_result if isinstance(root_result, dict) else {}
    terminal_result = state.get("terminal_result")
    terminal_result = terminal_result if isinstance(terminal_result, dict) else {}
    status = str(state.get("status") or "running")
    if status == "terminal_pending_persist":
        status = "running"
    output = (
        root_result.get("answer")
        or terminal_result.get("output")
        or terminal_result.get("answer")
        or ""
    )
    return {
        "run_id": str(run_id),
        "kind": run_kind.upper(),
        "status": status,
        "sequence": 0,
        "output": str(output or ""),
        "activity": None,
        "active_tools": [],
        "active_agents": [],
        "completed_agents": [],
        "current_route": None,
        "usage": state.get("usage") if isinstance(state.get("usage"), dict) else {},
        "result": root_result or terminal_result or None,
        "updated_at": state.get("updated_at") or _now_iso(),
        "realtime_available": True,
    }


def _public_event(event: ExecutionEvent) -> tuple[str, dict[str, Any]]:
    payload = deepcopy(event.payload)
    visibility = str(payload.get("visibility") or "public").lower()
    if visibility in {"internal", "private", "debug"}:
        return "run.progress", {}

    if event.event_type == "token":
        if (
            payload.get("visibility", "assistant") != "assistant"
            or payload.get("channel", "final") != "final"
        ):
            return "run.progress", {}
        return event.event_type, payload

    if event.event_type == "tool_call_started":
        for key in ("input", "arguments", "headers", "authorization"):
            payload.pop(key, None)
    elif event.event_type == "tool_call_completed":
        for key in ("output", "result", "response", "headers", "authorization"):
            payload.pop(key, None)
    elif event.event_type == "agent_invocation_completed":
        for key in ("output", "parsed_output", "tool_calls", "sources"):
            payload.pop(key, None)

    return event.event_type, payload


def reduce_projection(
    projection: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    *,
    sequence: int,
    occurred_at: str,
) -> dict[str, Any]:
    state = deepcopy(projection)
    state["sequence"] = sequence
    state["updated_at"] = occurred_at or _now_iso()

    if event_type in {"agent.run.accepted", "execution_started"}:
        state["status"] = "running"
    elif event_type == "meta":
        for key in ("trace_id", "session_id", "agent_id", "project_id"):
            if payload.get(key) is not None:
                state[key] = payload[key]
    elif event_type == "token":
        content = payload.get("content")
        if isinstance(content, str):
            state["output"] = str(state.get("output") or "") + content
    elif event_type == "token_retract":
        size = int(payload.get("content_length") or 0)
        if size > 0:
            output = str(state.get("output") or "")
            state["output"] = output[:-size] if size < len(output) else ""
    elif event_type == "agent_activity":
        state["activity"] = {
            key: payload.get(key)
            for key in ("status", "phase", "message", "tool_name")
            if payload.get(key) is not None
        }
    elif event_type == "tool_call_started":
        tool_name = payload.get("tool_name") or payload.get("name")
        if tool_name:
            tools = set(_as_list(state.get("active_tools")))
            tools.add(str(tool_name))
            state["active_tools"] = sorted(tools)
    elif event_type == "tool_call_completed":
        tool_name = payload.get("tool_name") or payload.get("name")
        if tool_name:
            tools = set(_as_list(state.get("active_tools")))
            tools.discard(str(tool_name))
            state["active_tools"] = sorted(tools)
    elif event_type == "agent_invocation_started":
        agent_id = payload.get("agent_id") or payload.get("label")
        if agent_id:
            active = set(_as_list(state.get("active_agents")))
            active.add(str(agent_id))
            state["active_agents"] = sorted(active)
    elif event_type in {"agent_invocation_completed", "agent_invocation_failed"}:
        agent_id = payload.get("agent_id") or payload.get("label")
        if agent_id:
            active = set(_as_list(state.get("active_agents")))
            completed = set(_as_list(state.get("completed_agents")))
            active.discard(str(agent_id))
            completed.add(str(agent_id))
            state["active_agents"] = sorted(active)
            state["completed_agents"] = sorted(completed)
    elif event_type in {"network.route.selected", "route.selected"}:
        state["current_route"] = payload.get("route") or payload.get("target")
    elif event_type == "usage":
        state["usage"] = deepcopy(payload)
    elif event_type in {"done", "execution_completed"}:
        state["status"] = "completed"
        result = payload.get("result")
        state["result"] = deepcopy(result if isinstance(result, dict) else payload)
        answer = payload.get("answer") or payload.get("output")
        if isinstance(answer, str):
            state["output"] = answer
        state["activity"] = None
        state["active_tools"] = []
        state["active_agents"] = []
    elif event_type in {"error", "execution_failed"}:
        state["status"] = "uncertain" if payload.get("uncertain") else "failed"
        state["error"] = {
            key: payload.get(key)
            for key in ("code", "message", "failure_code", "trace_id")
            if payload.get(key) is not None
        }
        state["activity"] = None
        state["active_tools"] = []
        state["active_agents"] = []
    elif event_type in {"cancelled", "execution_cancelled"}:
        state["status"] = "cancelled"
        state["activity"] = None
        state["active_tools"] = []
        state["active_agents"] = []

    return state


class RuntimeEventPublisher:
    """Best-effort hot event publisher with batched projection checkpoints.

    Runtime event delivery is observability infrastructure. Failure to publish here
    must not turn a successful Agent/Network execution into a failed Run.
    """

    def __init__(
        self,
        store: ExecutionStateStore,
        *,
        projection_interval_seconds: float = 0.2,
        maxlen: int = 2000,
    ) -> None:
        self._store = store
        self._projection_interval_seconds = max(0.0, projection_interval_seconds)
        self._maxlen = max(100, maxlen)
        self._last_projection_write: dict[UUID, float] = {}
        self._projection_lock = asyncio.Lock()

    @property
    def store(self) -> ExecutionStateStore:
        return self._store

    async def publish(
        self,
        run_id: UUID,
        run_kind: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        force_projection: bool | None = None,
    ) -> str | None:
        try:
            cursor = await self._store.append_event(
                run_id,
                event_type,
                payload,
                maxlen=self._maxlen,
            )
            now = time.monotonic()
            force = (
                event_type in _STRUCTURAL_EVENTS
                if force_projection is None
                else force_projection
            )
            last = self._last_projection_write.get(run_id, 0.0)
            if force or now - last >= self._projection_interval_seconds:
                await self._checkpoint(run_id, run_kind)
                self._last_projection_write[run_id] = now
            return cursor
        except Exception as exc:
            logger.warning(
                "Runtime event publication degraded run_id=%s event=%s: %s",
                run_id,
                event_type,
                exc,
            )
            return None

    async def _checkpoint(self, run_id: UUID, run_kind: str) -> None:
        async with self._projection_lock:
            hot = await self._store.get(run_id)
            if not hot:
                return
            high_watermark = int(hot.get("event_sequence") or 0)
            saved = hot.get("runtime_projection")
            projection = (
                deepcopy(saved)
                if isinstance(saved, dict)
                else initial_projection(run_id, run_kind, hot)
            )
            sequence = int(projection.get("sequence") or 0)
            if high_watermark <= sequence:
                return
            events = await self._store.list_events_after(
                run_id,
                sequence,
                through_sequence=high_watermark,
                limit=max(self._maxlen, high_watermark - sequence + 1),
            )
            for event in events:
                public_type, public_payload = _public_event(event)
                projection = reduce_projection(
                    projection,
                    public_type,
                    public_payload,
                    sequence=event.sequence,
                    occurred_at=event.occurred_at,
                )
            if events and events[-1].sequence == high_watermark:
                await self._store.update(run_id, {"runtime_projection": projection})


DurableFallback = Callable[[], Awaitable[dict[str, Any] | None]]


class RuntimeStreamReader:
    """Attach to one Run as current state followed by a lossless live tail."""

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
            state["sequence"] = int(state.get("sequence") or 0)
            state["realtime_available"] = False
            logger.info(
                "Runtime reattach state resolved",
                extra={
                    "run_id": str(run_id),
                    "run_kind": run_kind.upper(),
                    "realtime_available": False,
                    "high_watermark": 0,
                    "projection_sequence": int(state.get("sequence") or 0),
                    "projection_lag": 0,
                    "catchup_events": 0,
                    "attach_latency_ms": round((time.perf_counter() - started) * 1000, 3),
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
                    f"Runtime event history was trimmed before projection catch-up "
                    f"run_id={run_id} projection={projection_sequence} first={first_sequence}"
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
            for event in events:
                public_type, public_payload = _public_event(event)
                projection = reduce_projection(
                    projection,
                    public_type,
                    public_payload,
                    sequence=event.sequence,
                    occurred_at=event.occurred_at,
                )
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
    ) -> AsyncIterator[RuntimeStreamFrame]:
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
            sequence = int(projection.get("sequence") or 0)
            state_frame = RuntimeStreamFrame("run.state", projection, sequence=sequence)
            frame_count += 1
            approx_stream_bytes += _frame_size(state_frame)
            yield state_frame

            status = str(projection.get("status") or "").lower()
            if status in _TERMINAL_STATUSES:
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
                    logger.warning("Runtime live tail unavailable run_id=%s: %s", run_id, exc)
                    unavailable_frame = RuntimeStreamFrame(
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
                        heartbeat = RuntimeStreamFrame(
                            "heartbeat",
                            {"run_id": str(run_id), "ts": _now_iso()},
                        )
                        frame_count += 1
                        approx_stream_bytes += _frame_size(heartbeat)
                        yield heartbeat
                    continue

                for event in events:
                    cursor = event.cursor
                    public_type, public_payload = _public_event(event)
                    projection = reduce_projection(
                        projection,
                        public_type,
                        public_payload,
                        sequence=event.sequence,
                        occurred_at=event.occurred_at,
                    )
                    frame = RuntimeStreamFrame(
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
                    if status in _TERMINAL_STATUSES:
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
                    "stream_duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
