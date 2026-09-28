from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import uuid6

from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionBatch


def _message_id(message: Any) -> str | None:
    value = getattr(message, "id", None)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _message_fingerprint(message: Any) -> str:
    payload = {
        "type": type(message).__name__,
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "tool_call_id": getattr(message, "tool_call_id", None),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _with_message_id(message: Any, message_id: str) -> Any:
    copier = getattr(message, "model_copy", None)
    if callable(copier):
        return copier(update={"id": message_id})
    clone = deepcopy(message)
    try:
        setattr(clone, "id", message_id)
    except (AttributeError, TypeError) as exc:
        raise TypeError(
            f"Runtime message type {type(message).__name__} does not support stable identity"
        ) from exc
    return clone


def ensure_stable_message_ids(messages: list[Any]) -> list[Any]:
    """Ensure deterministic IDs for input messages without index-based identity."""

    occurrences: dict[str, int] = {}
    normalized: list[Any] = []
    for message in messages:
        if _message_id(message) is not None:
            normalized.append(message)
            continue
        fingerprint = _message_fingerprint(message)
        occurrence = occurrences.get(fingerprint, 0)
        occurrences[fingerprint] = occurrence + 1
        message_id = f"woobe-input-{fingerprint[:24]}-{occurrence}"
        try:
            normalized.append(_with_message_id(message, message_id))
        except TypeError:
            # Strategy inputs may contain framework-neutral/opaque values used by
            # custom Strategies. Stable identity is required only for message
            # objects that can participate in Runtime compaction/recovery.
            normalized.append(message)
    return normalized


def ensure_runtime_message_id(message: Any) -> Any:
    """Assign an opaque durable ID to a newly produced runtime message."""

    if _message_id(message) is not None:
        return message
    return _with_message_id(message, f"woobe-runtime-{uuid6.uuid7()}")


def _failure_context(
    context: dict[str, Any] | None,
    *,
    partial_result_available: bool,
) -> dict[str, Any]:
    return {
        **(context or {}),
        "partial_result_available": partial_result_available,
    }


@dataclass(slots=True)
class StrategyRuntimeState:
    """Operational execution state hidden from concrete Strategies."""

    execution: InstrumentedExecution = field(
        default_factory=lambda: InstrumentedExecution(result=None)
    )
    call_index: int = 0
    messages: list[Any] = field(default_factory=list)
    base_message_count: int = 0
    context_contributions: dict[str, Any] = field(default_factory=dict)
    context_replacements: dict[str, tuple[str, ...]] = field(default_factory=dict)
    last_model_message: Any | None = None

    def __post_init__(self) -> None:
        self.messages = ensure_stable_message_ids(list(self.messages))

    def next_call_index(self) -> int:
        self.call_index += 1
        return self.call_index

    def record_model_call(self, call: dict[str, Any]) -> None:
        self.call_index = max(self.call_index, int(call.get("call_index") or 0))
        self.execution.llm_calls.append(call)
        self.execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

    def record_model_message(self, message: Any) -> None:
        message = ensure_runtime_message_id(message)
        self.last_model_message = message
        self.messages.append(message)

    def absorb_model_error(self, exc: InstrumentedExecutionError) -> None:
        self.execution.llm_calls.extend(exc.llm_calls)
        self.execution.timeline.extend(exc.timeline)
        self.execution.failure_context = _failure_context(
            exc.failure_context,
            partial_result_available=bool(self.execution.tool_calls),
        )

    def record_knowledge_call(
        self,
        call: dict[str, Any],
        sources: tuple[Any, ...],
    ) -> None:
        self.execution.knowledge_calls.append(call)
        self.execution.timeline.append(
            {
                "kind": "knowledge",
                "occurred_at": call["occurred_at"],
                "payload": call,
            }
        )
        known = {
            source.model_dump_json()
            for source in self.execution.sources
            if hasattr(source, "model_dump_json")
        }
        for source in sources:
            identity = (
                source.model_dump_json()
                if hasattr(source, "model_dump_json")
                else repr(source)
            )
            if identity in known:
                continue
            self.execution.sources.append(source)
            known.add(identity)

    def record_tool_batch(self, batch: ToolExecutionBatch) -> None:
        self.execution.tool_wall_latency_ms += batch.wall_latency_ms
        for info, message, payload in batch.results:
            self.execution.tool_calls.append(info)
            self.execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            self.execution.timeline.append(
                {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
            )
            self.messages.append(ensure_runtime_message_id(message))
