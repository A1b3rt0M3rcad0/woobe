from __future__ import annotations

import json

from shared.runtime.contracts import RuntimeFrame


def format_sse_frame(frame: RuntimeFrame) -> str:
    prefix = f"id: {frame.sequence}\n" if frame.sequence is not None else ""
    payload = {"type": frame.event_type, **frame.data}
    return (
        f"{prefix}event: {frame.event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    )
