from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import uuid6

from shared.observability.metrics import runtime_metrics

from shared.runtime.contracts import RUNTIME_STREAM_PROTOCOL_VERSION
RUNTIME_STREAM_HEARTBEAT_SECONDS = 10.0
_DURABLE_OUTPUT_BATCH_BYTES = 16_384
_DURABLE_OUTPUT_FLUSH_INTERVAL_SECONDS = 0.2

_TEXT_BLOCK_TYPES = {"", "text", "output_text"}
_INTERNAL_BLOCK_TYPES = {
    "reasoning",
    "reasoning_content",
    "thinking",
    "thought",
    "internal",
    "tool_use",
    "server_tool_call",
    "web_search_call",
}
_FINAL_RESPONSE_PHASES = {"response_generation", "final_response_generation"}
_PROVIDER_CONTROL_TOKENS = (
    "<｜end▁of▁sentence｜>",
    "<|endoftext|>",
    "<|eot_id|>",
)


def _stream_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def normalize_assistant_text(value: str) -> str:
    normalized = value
    for token in _PROVIDER_CONTROL_TOKENS:
        normalized = normalized.replace(token, "")
    return normalized


def _normalize_content_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_assistant_text(value)
    if not isinstance(value, list):
        return value

    normalized_items: list[Any] = []
    for item in value:
        if isinstance(item, str):
            normalized_items.append(normalize_assistant_text(item))
            continue
        if not isinstance(item, dict):
            normalized_items.append(item)
            continue
        normalized_item = dict(item)
        for key in ("text", "content", "delta"):
            text = normalized_item.get(key)
            if isinstance(text, str):
                normalized_item[key] = normalize_assistant_text(text)
        normalized_items.append(normalized_item)
    return normalized_items


def normalize_llm_result_content(result: Any) -> Any:
    content = getattr(result, "content", None)
    normalized = _normalize_content_value(content)
    if normalized == content:
        return result

    model_copy = getattr(result, "model_copy", None)
    if callable(model_copy):
        return model_copy(update={"content": normalized})
    try:
        setattr(result, "content", normalized)
    except (AttributeError, TypeError, ValueError):
        return result
    return result


def _longest_control_token_prefix_suffix(value: str) -> int:
    longest = 0
    for token in _PROVIDER_CONTROL_TOKENS:
        max_size = min(len(value), len(token) - 1)
        for size in range(max_size, 0, -1):
            if value.endswith(token[:size]):
                longest = max(longest, size)
                break
    return longest


class _ProviderControlTokenFilter:
    def __init__(self) -> None:
        self._buffer = ""

    def push(self, content: str) -> str:
        self._buffer = normalize_assistant_text(self._buffer + content)
        pending_size = _longest_control_token_prefix_suffix(self._buffer)
        if pending_size:
            visible = self._buffer[:-pending_size]
            self._buffer = self._buffer[-pending_size:]
            return visible
        visible = self._buffer
        self._buffer = ""
        return visible

    def flush(self) -> str:
        visible = normalize_assistant_text(self._buffer)
        self._buffer = ""
        return visible


@dataclass(frozen=True)
class RuntimeStreamEvent:
    event_type: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=_stream_utc_iso)
    sequence: int | None = None
    run_id: UUID | None = None
    session_id: UUID | None = None


@dataclass(frozen=True)
class RuntimeStreamTextPart:
    content: str
    visibility: str = "assistant"
    channel: str = "final"
    redacted: bool = False


@dataclass
class RuntimeStreamChannel:
    request_id: UUID = field(default_factory=uuid4)
    queue: asyncio.Queue[RuntimeStreamEvent] = field(default_factory=asyncio.Queue)
    started_monotonic: float = field(default_factory=time.monotonic)
    run_id: UUID | None = None
    sequence: int = 0
    trace_id: UUID | None = None
    session_id: UUID | None = None
    project_id: UUID | None = None
    agent_id: UUID | None = None
    ttft_ms: int | None = None
    terminal_emitted: bool = False
    public_output: str = ""
    latest_usage: dict[str, Any] | None = None
    _observer_queues: set[asyncio.Queue[RuntimeStreamEvent]] = field(
        default_factory=set,
        repr=False,
    )
    _durable_output_recorder: Any | None = field(default=None, repr=False)
    _durable_output_parts: list[str] = field(default_factory=list, repr=False)
    _durable_output_message_id: UUID | None = field(default=None, repr=False)
    _durable_output_phase: str | None = field(default=None, repr=False)
    _durable_output_bytes: int = field(default=0, repr=False)
    _durable_output_last_flush: float = field(
        default_factory=time.monotonic,
        repr=False,
    )

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

    def subscribe(self) -> asyncio.Queue[RuntimeStreamEvent]:
        queue: asyncio.Queue[RuntimeStreamEvent] = asyncio.Queue()
        self._observer_queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RuntimeStreamEvent]) -> None:
        self._observer_queues.discard(queue)

    def _resolve_durable_output_recorder(self) -> Any | None:
        if self._durable_output_recorder is not None:
            return self._durable_output_recorder

        # Resolve lazily while the Agent execution context is still bound, then keep
        # the recorder on the channel so cancellation/error cleanup can flush output
        # even after the request execution ContextVar has already been reset.
        from modules.agent.application.interfaces.execution_context import current_execution

        context = current_execution.get()
        recorder = getattr(context, "run_event_recorder", None) if context else None
        if recorder is not None:
            self._durable_output_recorder = recorder
        return recorder

    async def append_durable_output(
        self,
        content: str,
        *,
        message_id: UUID | None = None,
        phase: str | None = None,
    ) -> None:
        recorder = self._resolve_durable_output_recorder()
        if recorder is None or not content:
            return

        if message_id is not None:
            self._durable_output_message_id = message_id
        if phase is not None:
            self._durable_output_phase = phase
        self._durable_output_parts.append(content)
        self._durable_output_bytes += len(content.encode("utf-8"))
        elapsed = time.monotonic() - self._durable_output_last_flush
        if (
            self._durable_output_bytes >= _DURABLE_OUTPUT_BATCH_BYTES
            or elapsed >= _DURABLE_OUTPUT_FLUSH_INTERVAL_SECONDS
        ):
            await self.flush_durable_output()

    async def flush_durable_output(self) -> None:
        recorder = self._resolve_durable_output_recorder()
        if recorder is None or not self._durable_output_parts:
            return

        content = "".join(self._durable_output_parts)
        self._durable_output_parts = []
        self._durable_output_bytes = 0
        self._durable_output_last_flush = time.monotonic()
        payload: dict[str, Any] = {
            "content": content,
            "channel": "final",
            "visibility": "assistant",
            "output_mode": "final",
        }
        if self._durable_output_message_id is not None:
            payload["message_id"] = str(self._durable_output_message_id)
        if self._durable_output_phase is not None:
            payload["phase"] = self._durable_output_phase
        await recorder.emit("output.delta.batch", payload)

    async def retract_durable_output(
        self,
        *,
        content_length: int,
        token_count: int,
        phase: str,
        reason: str,
        provider: str,
        model_name: str,
        message_id: UUID | None = None,
    ) -> None:
        recorder = self._resolve_durable_output_recorder()
        if recorder is None or content_length <= 0:
            return

        # The durable projection must observe the candidate output before the
        # retraction that invalidates it, matching the public runtime stream order.
        await self.flush_durable_output()
        await recorder.emit(
            "output.retracted",
            {
                "content_length": content_length,
                "token_count": token_count,
                "phase": phase,
                "reason": reason,
                "provider": provider,
                "model": model_name,
                "message_id": str(message_id) if message_id is not None else None,
            },
        )

    def _capture_public_state(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "token":
            if (
                payload.get("visibility", "assistant") == "assistant"
                and payload.get("channel", "final") == "final"
            ):
                content = payload.get("content")
                if isinstance(content, str):
                    self.public_output += content
            return

        if event_type == "token_retract":
            size = payload.get("content_length")
            if isinstance(size, int) and not isinstance(size, bool) and size > 0:
                self.public_output = (
                    self.public_output[:-size]
                    if size < len(self.public_output)
                    else ""
                )
            return

        if event_type == "usage":
            usage = payload.get("usage")
            candidate = usage if isinstance(usage, dict) else payload
            self.latest_usage = dict(candidate)
            return

        if event_type == "done":
            answer = payload.get("answer")
            if isinstance(answer, str):
                self.public_output = answer
            usage = payload.get("usage")
            if isinstance(usage, dict):
                self.latest_usage = dict(usage)

    async def emit(self, event_type: str, **payload: Any) -> None:
        if self.terminal_emitted:
            return
        self._capture_public_state(event_type, payload)
        if event_type in {"done", "error", "cancelled"}:
            self.terminal_emitted = True
        semantic = self.run_id is not None and self.session_id is not None
        if semantic:
            self.sequence += 1
        event = RuntimeStreamEvent(
            event_type=event_type,
            payload={"request_id": str(self.request_id), **payload},
            sequence=self.sequence if semantic else None,
            run_id=self.run_id if semantic else None,
            session_id=self.session_id if semantic else None,
        )
        await self.queue.put(event)
        for observer_queue in tuple(self._observer_queues):
            observer_queue.put_nowait(event)

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


async def emit_agent_activity(
    status: str,
    *,
    phase: str | None = None,
    message: str | None = None,
    tool_name: str | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status}
    if phase is not None:
        payload["phase"] = phase
    if message is not None:
        payload["message"] = message
    if tool_name is not None:
        payload["tool_name"] = tool_name
    await emit_runtime_event("agent_activity", **payload)


def _text_from_block(block: dict[str, Any]) -> str:
    for key in ("text", "content", "delta"):
        value = block.get(key)
        if isinstance(value, str):
            return value
    return ""


def _classify_text_block(block: dict[str, Any]) -> RuntimeStreamTextPart | None:
    block_type = str(block.get("type") or "").lower()
    text = _text_from_block(block)
    if not text:
        return None
    if block_type in _INTERNAL_BLOCK_TYPES:
        return RuntimeStreamTextPart(
            content=text,
            visibility="internal",
            channel=block_type or "internal",
            redacted=True,
        )
    if block_type not in _TEXT_BLOCK_TYPES:
        return RuntimeStreamTextPart(
            content=text,
            visibility="internal",
            channel=block_type or "internal",
            redacted=True,
        )
    return RuntimeStreamTextPart(content=text)


def extract_chunk_text_parts(chunk: Any) -> list[RuntimeStreamTextPart]:
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return [RuntimeStreamTextPart(content=content)] if content else []
    if not isinstance(content, list):
        return []

    parts: list[RuntimeStreamTextPart] = []
    for block in content:
        if isinstance(block, str):
            if block:
                parts.append(RuntimeStreamTextPart(content=block))
        elif isinstance(block, dict):
            part = _classify_text_block(block)
            if part is not None:
                parts.append(part)
    return parts


def extract_chunk_text(chunk: Any) -> str:
    return "".join(
        part.content
        for part in extract_chunk_text_parts(chunk)
        if part.visibility == "assistant" and part.channel == "final"
    )


def _combine_chunks(accumulated: Any | None, chunk: Any) -> Any:
    if accumulated is None:
        return chunk
    try:
        return accumulated + chunk
    except (TypeError, ValueError):
        return chunk


def _result_has_tool_calls(result: Any | None) -> bool:
    return bool(
        getattr(result, "tool_calls", None)
        or getattr(result, "tool_call_chunks", None)
    )


def _is_final_response_phase(phase: str) -> bool:
    return phase in _FINAL_RESPONSE_PHASES


def _is_capability_selection_phase(phase: str) -> bool:
    return phase == "capability_response_generation" or phase.startswith("tool_followup_")


def _effective_output_mode(phase: str, output_mode: str | None) -> str:
    if output_mode is not None:
        normalized = output_mode.strip().lower()
        if normalized not in {"internal", "intermediate", "final"}:
            raise ValueError(f"Unsupported Strategy output mode: {output_mode}")
        return normalized
    if _is_final_response_phase(phase) or _is_capability_selection_phase(phase):
        return "final"
    return "internal"


def _phase_activity_label(phase: str) -> str:
    normalized = " ".join(part for part in phase.split("_") if part).strip()
    return normalized.capitalize() if normalized else "Working"


def _activity_for_phase(
    phase: str,
    *,
    output_mode: str | None = None,
) -> tuple[str, str]:
    if phase == "capability_response_generation":
        return "generating_answer", "Generating response..."
    if phase.startswith("tool_followup_"):
        return "generating_answer", "Generating response..."
    if _is_final_response_phase(phase):
        return "generating_answer", "Generating response..."
    if phase == "json_repair":
        return "formatting_response", "Formatting structured response..."

    label = _phase_activity_label(phase)
    mode = _effective_output_mode(phase, output_mode)
    if mode == "final":
        return "generating_answer", f"Generating {label.lower()}..."
    return "thinking", f"{label}..."


def _output_message_id(mode: str) -> UUID | None:
    if mode == "internal":
        return None

    from modules.agent.application.interfaces.execution_context import current_execution

    context = current_execution.get()
    if mode == "final":
        if context is not None:
            if context.output_message_id is None:
                context.output_message_id = uuid6.uuid7()
            return context.output_message_id
        return uuid6.uuid7()
    return uuid6.uuid7()


async def _record_intermediate_message(
    *,
    message_id: UUID,
    content: str,
    phase: str,
    provider: str,
    model_name: str,
    partial: bool = False,
) -> dict[str, Any]:
    completed_at = _stream_utc_iso()
    payload: dict[str, Any] = {
        "message_id": str(message_id),
        "content": content,
        "phase": phase,
        "output_mode": "intermediate",
        "provider": provider,
        "model": model_name,
        "partial": partial,
        "completed_at": completed_at,
    }

    from modules.agent.application.interfaces.execution_context import current_execution

    context = current_execution.get()
    if context is not None:
        if context.intermediate_messages is None:
            context.intermediate_messages = []
        context.intermediate_messages.append(dict(payload))
        recorder = getattr(context, "run_event_recorder", None)
        if recorder is not None:
            await recorder.emit("assistant.message.completed", payload, durable=True)
    return payload


async def _emit_intermediate_token(
    channel: RuntimeStreamChannel,
    *,
    message_id: UUID,
    content: str,
    phase: str,
    provider: str,
    model_name: str,
) -> None:
    channel.mark_first_token(provider=provider, model=model_name)
    await channel.emit(
        "assistant_message_delta",
        message_id=str(message_id),
        content=content,
        phase=phase,
        output_mode="intermediate",
        provider=provider,
        model=model_name,
    )


async def _complete_intermediate_message(
    channel: RuntimeStreamChannel | None,
    *,
    message_id: UUID,
    content: str,
    phase: str,
    provider: str,
    model_name: str,
    partial: bool = False,
) -> None:
    if not content:
        return
    payload = await _record_intermediate_message(
        message_id=message_id,
        content=content,
        phase=phase,
        provider=provider,
        model_name=model_name,
        partial=partial,
    )
    if channel is not None:
        await channel.emit("assistant_message_completed", **payload)


async def _emit_visible_token(
    channel: RuntimeStreamChannel,
    *,
    content: str,
    phase: str,
    provider: str,
    model_name: str,
    message_id: UUID | None = None,
) -> None:
    channel.mark_first_token(provider=provider, model=model_name)
    await channel.emit(
        "token",
        content=content,
        visibility="assistant",
        channel="final",
        phase=phase,
        provider=provider,
        model_name=model_name,
        message_id=str(message_id) if message_id is not None else None,
        output_mode="final",
    )
    await channel.append_durable_output(
        content,
        message_id=message_id,
        phase=phase,
    )


async def _retract_streamed_tokens(
    channel: RuntimeStreamChannel,
    *,
    streamed_visible_tokens: list[str],
    phase: str,
    reason: str,
    provider: str,
    model_name: str,
    message_id: UUID | None = None,
) -> None:
    if not streamed_visible_tokens:
        return
    content_length = sum(len(content) for content in streamed_visible_tokens)
    await channel.emit(
        "token_retract",
        phase=phase,
        reason=reason,
        content_length=content_length,
        token_count=len(streamed_visible_tokens),
        provider=provider,
        model_name=model_name,
        message_id=str(message_id) if message_id is not None else None,
    )
    await channel.retract_durable_output(
        content_length=content_length,
        token_count=len(streamed_visible_tokens),
        phase=phase,
        reason=reason,
        provider=provider,
        model_name=model_name,
        message_id=message_id,
    )


async def invoke_model_with_optional_streaming(
    *,
    model: Any,
    messages: list,
    phase: str,
    provider: str,
    model_name: str,
    output_mode: str | None = None,
) -> Any:
    mode = _effective_output_mode(phase, output_mode)
    message_id = _output_message_id(mode)
    channel = current_runtime_stream.get()

    if channel is None:
        try:
            result = normalize_llm_result_content(await model.ainvoke(messages))
            if mode == "intermediate" and message_id is not None:
                content = extract_chunk_text(result)
                await _complete_intermediate_message(
                    None,
                    message_id=message_id,
                    content=content,
                    phase=phase,
                    provider=provider,
                    model_name=model_name,
                )
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            runtime_metrics.increment_provider_failure(
                provider=provider,
                model=model_name,
            )
            raise

    activity_status, activity_message = _activity_for_phase(
        phase,
        output_mode=output_mode,
    )
    await channel.emit(
        "agent_activity",
        status=activity_status,
        phase=phase,
        message=activity_message,
        provider=provider,
        model=model_name,
    )

    accumulated = None
    pending_visible_tokens: list[str] = []
    streamed_visible_tokens: list[str] = []
    control_filter = _ProviderControlTokenFilter()

    async def emit_visible(content: str) -> None:
        streamed_visible_tokens.append(content)
        if mode == "intermediate":
            assert message_id is not None
            await _emit_intermediate_token(
                channel,
                message_id=message_id,
                content=content,
                phase=phase,
                provider=provider,
                model_name=model_name,
            )
            return
        if mode == "final":
            await _emit_visible_token(
                channel,
                content=content,
                phase=phase,
                provider=provider,
                model_name=model_name,
                message_id=message_id,
            )

    try:
        async for chunk in model.astream(messages):
            accumulated = _combine_chunks(accumulated, chunk)
            for part in extract_chunk_text_parts(chunk):
                if part.visibility != "assistant" or part.channel != "final":
                    continue
                visible_content = control_filter.push(part.content)
                if not visible_content:
                    continue
                if mode in {"intermediate", "final"}:
                    await emit_visible(visible_content)
                else:
                    pending_visible_tokens.append(visible_content)
    except asyncio.CancelledError:
        if mode == "intermediate" and message_id is not None and streamed_visible_tokens:
            await _complete_intermediate_message(
                channel,
                message_id=message_id,
                content="".join(streamed_visible_tokens),
                phase=phase,
                provider=provider,
                model_name=model_name,
                partial=True,
            )
        await channel.flush_durable_output()
        raise
    except Exception:
        if mode == "intermediate" and message_id is not None and streamed_visible_tokens:
            await _complete_intermediate_message(
                channel,
                message_id=message_id,
                content="".join(streamed_visible_tokens),
                phase=phase,
                provider=provider,
                model_name=model_name,
                partial=True,
            )
        elif (
            mode == "final"
            and _is_capability_selection_phase(phase)
            and streamed_visible_tokens
        ):
            await _retract_streamed_tokens(
                channel,
                streamed_visible_tokens=streamed_visible_tokens,
                phase=phase,
                reason="capability_decision_failed",
                provider=provider,
                model_name=model_name,
                message_id=message_id,
            )
        await channel.flush_durable_output()
        runtime_metrics.increment_provider_failure(
            provider=provider,
            model=model_name,
        )
        raise

    trailing_content = control_filter.flush()
    if trailing_content:
        if mode in {"intermediate", "final"}:
            await emit_visible(trailing_content)
        else:
            pending_visible_tokens.append(trailing_content)

    if accumulated is None:
        runtime_metrics.increment_provider_failure(
            provider=provider,
            model=model_name,
        )
        raise RuntimeError("Provider stream completed without a response")

    accumulated = normalize_llm_result_content(accumulated)

    if mode == "intermediate" and message_id is not None and streamed_visible_tokens:
        await _complete_intermediate_message(
            channel,
            message_id=message_id,
            content="".join(streamed_visible_tokens),
            phase=phase,
            provider=provider,
            model_name=model_name,
        )
    elif mode == "final" and _result_has_tool_calls(accumulated) and streamed_visible_tokens:
        await _retract_streamed_tokens(
            channel,
            streamed_visible_tokens=streamed_visible_tokens,
            phase=phase,
            reason="tool_call_selected",
            provider=provider,
            model_name=model_name,
            message_id=message_id,
        )
    elif mode == "final" and pending_visible_tokens and not _result_has_tool_calls(accumulated):
        for content in pending_visible_tokens:
            await _emit_visible_token(
                channel,
                content=content,
                phase=phase,
                provider=provider,
                model_name=model_name,
                message_id=message_id,
            )

    await channel.flush_durable_output()
    return accumulated
