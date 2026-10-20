from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeAlias

from woobe.errors import WoobeProtocolError
from woobe.events import RUNTIME_STREAM_PROTOCOL_VERSION, WoobeEvent

_CONTROL_TYPES = {"heartbeat", "run.realtime_unavailable", "error", "protocol.control"}
_SEMANTIC_FORBIDDEN_TYPES = {"heartbeat", "run.realtime_unavailable"}
_MAX_SAFE_INTEGER = (1 << 53) - 1


@dataclass(frozen=True, slots=True)
class SseFrame:
    event: str
    data: dict[str, Any]
    event_id: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeControlFrame:
    protocol_version: int
    type: str
    occurred_at: datetime
    payload: dict[str, Any]


ParsedRuntimeFrame: TypeAlias = WoobeEvent | RuntimeControlFrame


class SseDecoder:
    """Small SSE decoder for the subset used by the Woobe Runtime API."""

    def __init__(self) -> None:
        self._event: str | None = None
        self._event_id: str | None = None
        self._data: list[str] = []

    def feed_line(self, line: str) -> SseFrame | None:
        if line == "":
            return self._flush()
        if line.startswith(":"):
            return None

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]

        if field == "event":
            self._event = value
        elif field == "id":
            self._event_id = value
        elif field == "data":
            self._data.append(value)
        return None

    def finish(self) -> SseFrame | None:
        return self._flush()

    def _flush(self) -> SseFrame | None:
        if not self._data:
            self._reset()
            return None

        raw_data = "\n".join(self._data)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            self._reset()
            raise WoobeProtocolError("Runtime SSE frame contains invalid JSON") from exc

        event = self._event
        event_id = self._event_id
        self._reset()

        if not isinstance(data, dict):
            raise WoobeProtocolError("Runtime SSE data must be a JSON object")
        if not event:
            candidate = data.get("type")
            event = candidate if isinstance(candidate, str) and candidate else "message"
        return SseFrame(event=event, data=data, event_id=event_id)

    def _reset(self) -> None:
        self._event = None
        self._event_id = None
        self._data = []


def parse_runtime_frame(frame: SseFrame) -> ParsedRuntimeFrame:
    data = frame.data
    if data.get("protocol_version") != RUNTIME_STREAM_PROTOCOL_VERSION:
        raise WoobeProtocolError(
            f"Unsupported runtime stream protocol version: {data.get('protocol_version')!r}"
        )

    event_type = _required_text(data, "type")
    occurred_at = _required_datetime(data, "occurred_at")
    if frame.event and frame.event != event_type:
        raise WoobeProtocolError("SSE event type differs from its envelope")

    payload_value = data.get("payload")
    payload = payload_value if isinstance(payload_value, dict) else None
    is_control = all(
        name not in data for name in ("event_id", "run_id", "session_id", "sequence")
    )

    if is_control:
        if frame.event_id is not None or event_type not in _CONTROL_TYPES:
            raise WoobeProtocolError("Invalid transport frame")
        return RuntimeControlFrame(
            protocol_version=RUNTIME_STREAM_PROTOCOL_VERSION,
            type=event_type,
            occurred_at=occurred_at,
            payload=payload or {},
        )

    sequence = data.get("sequence")
    if (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence < 0
        or sequence > _MAX_SAFE_INTEGER
        or payload is None
        or data.get("run_kind") not in {"AGENT", "NETWORK"}
        or event_type in _SEMANTIC_FORBIDDEN_TYPES
    ):
        raise WoobeProtocolError("Invalid semantic runtime event envelope")

    if frame.event_id is not None and frame.event_id != str(sequence):
        raise WoobeProtocolError("SSE cursor differs from semantic sequence")

    return WoobeEvent(
        protocol_version=RUNTIME_STREAM_PROTOCOL_VERSION,
        event_id=_required_text(data, "event_id"),
        run_id=_required_text(data, "run_id"),
        session_id=_required_text(data, "session_id"),
        run_kind=data["run_kind"],
        sequence=sequence,
        type=event_type,
        occurred_at=occurred_at,
        payload=payload,
    )


def _required_text(data: dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise WoobeProtocolError(f"Missing runtime event {name}")
    return value


def _required_datetime(data: dict[str, Any], name: str) -> datetime:
    value = _required_text(data, name)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WoobeProtocolError(f"Invalid runtime event {name}") from exc
