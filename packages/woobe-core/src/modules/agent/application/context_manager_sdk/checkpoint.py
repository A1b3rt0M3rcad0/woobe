from __future__ import annotations

from enum import StrEnum


class ContextCheckpointBoundary(StrEnum):
    """Durable boundaries meaningful to Context Manager algorithms."""

    SUMMARY = "context_summary_boundary"
    MANUAL = "context_manual_boundary"
