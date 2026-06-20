from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from shared.observability.metrics import runtime_metrics

RUNTIME_STREAM_PROTOCOL_VERSION = 1
RUNTIME_STREAM_HEARTBEAT_SECONDS = 10.0


def _stream_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RuntimeStreamEvent:
    event_type: str
    payload: dict[str, Any]


@dataclass
class RuntimeStreamChannel:
    request_id: UUID = field(default_factory=uuid4)
    queue: asyncio.Queue[RuntimeStreamEvent] = field(default_factory=asyncio.Queue)
    started_monotonic: float = field(default_factory=time.monotonic)
    trace_id: UUID | None = None
    session_id: UUID | None = None
    project_id: UUID | None = None
    agent_id: UUID | None = None
    ttft_ms: int | None = None
    terminal_emitted: bool = False

    def bind_execution(
        self,
        *,
        trace_id: UUID,
        session_id: UUID | None,
        project_id: UUID,
        agent_id: UUID,
    ) -> None:
        self.trace_id = trace_id
        self.session_id = session_id
        self.project_id = project_id
        self.agent_id = agent_id

    async def emit(self, event_type: str, **payload: Any) -> None:
        if self.terminal_emitted:
            return
        if event_type in {"done", "error", "cancelled"}:
            self.terminal_emitted = True
        await self.queue.put(
            RuntimeStreamEvent(
                event_type=event_type,
                payload={
                    "protocol_version": RUNTIME_STREAM_PROTOCOL_VERSION,
                    "request_id": str(self.request_id),
                    "occurred_at": _stream_utc_iso(),
                    **payload,
                },
            )
        )

    def mark_first_token(self, *, provider: str, model: str) -> None:
        if self.ttft_ms is not None:
            return
        self.ttft_ms = round((time.monotonic() - self.started_monotonic) * 1000)
        runtime_metrics.observe_ttft(
            provider=provider,
            model=model,
            milliseconds=self.ttft_ms,
        )


current_runtime_stream: ContextVar[RuntimeStreamChannel | None] = ContextVar(
    "current_runtime_stream",
    default=None,
)


def runtime_streaming_enabled() -> bool:
    return current_runtime_stream.get() is not None


async def emit_runtime_event(event_type: str, **payload: Any) -> None:
    channel = current_runtime_stream.get()
    if channel is not None:
        await channel.emit(event_type, **payload)


def extract_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text") or block.get("content")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _combine_chunks(accumulated: Any | None, chunk: Any) -> Any:
    if accumulated is None:
        return chunk
    try:
        return accumulated + chunk
    except (TypeError, ValueError):
        return chunk


async def invoke_model_with_optional_streaming(
    *,
    model: Any,
    messages: list,
    phase: str,
    provider: str,
    model_name: str,
) -> Any:
    channel = current_runtime_stream.get()
    if channel is None:
        try:
            return await model.ainvoke(messages)
        except asyncio.CancelledError:
            raise
        except Exception:
            runtime_metrics.increment_provider_failure(
                provider=provider,
                model=model_name,
            )
            raise

    accumulated = None
    try:
        async for chunk in model.astream(messages):
            accumulated = _combine_chunks(accumulated, chunk)
            text = extract_chunk_text(chunk)
            if text:
                channel.mark_first_token(provider=provider, model=model_name)
                await channel.emit(
                    "token",
                    content=text,
                    phase=phase,
                    provider=provider,
                    model=model_name,
                )
    except asyncio.CancelledError:
        raise
    except Exception:
        runtime_metrics.increment_provider_failure(
            provider=provider,
            model=model_name,
        )
        raise

    if accumulated is None:
        runtime_metrics.increment_provider_failure(
            provider=provider,
            model=model_name,
        )
        raise RuntimeError("Provider stream completed without a response")
    return accumulated
