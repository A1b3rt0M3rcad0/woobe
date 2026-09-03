"""Compatibility imports for the canonical ``shared.runtime`` package.

The former reattach implementation lived in this module. Runtime projection,
publishing, observation and SSE framing now have a single implementation under
``shared.runtime``. New production code must import from ``shared.runtime`` or its
submodules; this shim exists only while legacy import sites are migrated.
"""

from shared.runtime.contracts import RuntimeFrame
from shared.runtime.observer import (
    DurableFallback,
    RuntimeStreamGapError,
    RuntimeStreamReader,
)
from shared.runtime.projection import (
    _public_event,
    initial_projection,
    reduce_projection,
)
from shared.runtime.publisher import RuntimeEventPublisher
from shared.runtime.sse import format_sse_frame

RuntimeStreamFrame = RuntimeFrame

__all__ = [
    "DurableFallback",
    "RuntimeEventPublisher",
    "RuntimeStreamFrame",
    "RuntimeStreamGapError",
    "RuntimeStreamReader",
    "_public_event",
    "format_sse_frame",
    "initial_projection",
    "reduce_projection",
]
