from datetime import UTC

import pytest

from woobe._transport.sse import (
    RuntimeControlFrame,
    SseDecoder,
    SseFrame,
    parse_runtime_frame,
)
from woobe.errors import WoobeProtocolError
from woobe.events import WoobeEvent


def _semantic_data(**overrides):
    data = {
        "protocol_version": 2,
        "event_id": "evt-1",
        "run_id": "run-1",
        "session_id": "session-1",
        "run_kind": "AGENT",
        "sequence": 7,
        "type": "token",
        "occurred_at": "2026-09-16T20:30:00Z",
        "payload": {"content": "Olá"},
    }
    data.update(overrides)
    return data


def test_parse_semantic_runtime_event_v2() -> None:
    event = parse_runtime_frame(
        SseFrame(event="token", event_id="7", data=_semantic_data())
    )

    assert isinstance(event, WoobeEvent)
    assert event.protocol_version == 2
    assert event.run_id == "run-1"
    assert event.session_id == "session-1"
    assert event.run_kind == "AGENT"
    assert event.sequence == 7
    assert event.payload == {"content": "Olá"}
    assert event.occurred_at.tzinfo == UTC


def test_parse_transport_control_frame_without_semantic_identity() -> None:
    frame = parse_runtime_frame(
        SseFrame(
            event="heartbeat",
            data={
                "protocol_version": 2,
                "type": "heartbeat",
                "occurred_at": "2026-09-16T20:30:10Z",
            },
        )
    )

    assert isinstance(frame, RuntimeControlFrame)
    assert frame.type == "heartbeat"
    assert frame.payload == {}


@pytest.mark.parametrize(
    "frame",
    [
        SseFrame(event="token", event_id="7", data=_semantic_data(protocol_version=1)),
        SseFrame(event="done", event_id="7", data=_semantic_data()),
        SseFrame(event="token", event_id="6", data=_semantic_data()),
        SseFrame(event="token", event_id="7", data=_semantic_data(session_id=None)),
        SseFrame(event="token", event_id="7", data=_semantic_data(sequence=None)),
    ],
)
def test_invalid_runtime_v2_envelope_is_rejected(frame: SseFrame) -> None:
    with pytest.raises(WoobeProtocolError):
        parse_runtime_frame(frame)


def test_sse_decoder_keeps_transport_headers_separate() -> None:
    decoder = SseDecoder()

    assert decoder.feed_line("id: 7") is None
    assert decoder.feed_line("event: token") is None
    assert decoder.feed_line('data: {"protocol_version":2,"type":"token"}') is None

    frame = decoder.feed_line("")

    assert frame is not None
    assert frame.event == "token"
    assert frame.event_id == "7"
    assert frame.data["protocol_version"] == 2
