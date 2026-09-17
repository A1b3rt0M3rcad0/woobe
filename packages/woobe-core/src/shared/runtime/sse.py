from __future__ import annotations

import json

from shared.runtime.contracts import (
    RUNTIME_STREAM_PROTOCOL_VERSION, RuntimeFrame, RuntimeControlFrame, SemanticRuntimeEvent,
)


def format_sse_frame(frame: RuntimeFrame) -> str:
    envelope = {
        "protocol_version": RUNTIME_STREAM_PROTOCOL_VERSION,
        "type": frame.event_type,
        "occurred_at": frame.occurred_at,
    }
    prefix = ""
    if isinstance(frame, SemanticRuntimeEvent):
        envelope.update(
            event_id=frame.event_id, run_id=str(frame.run_id),
            session_id=str(frame.session_id), run_kind=frame.run_kind.value.upper(),
            sequence=frame.sequence, payload=frame.data,
        )
        prefix = f"id: {frame.sequence}\n"
    elif isinstance(frame, RuntimeControlFrame):
        if frame.data:
            envelope["payload"] = frame.data
    else:
        raise TypeError("Runtime frames must explicitly be semantic or transport")
    return (
        f"{prefix}event: {frame.event_type}\n"
        f"data: {json.dumps(envelope, ensure_ascii=False, default=str)}\n\n"
    )
