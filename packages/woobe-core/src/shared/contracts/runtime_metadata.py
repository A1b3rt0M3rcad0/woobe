"""Helpers for filtering worker-only fields from public runtime metadata."""

from typing import Any


def strip_untrusted_runtime_metadata(value: Any) -> dict[str, Any]:
    """Remove worker-only Network fields supplied through a public request body."""
    metadata = dict(value) if isinstance(value, dict) else {}
    metadata.pop("__network_artifact_runtime__", None)
    if metadata.get("source") == "network_runtime":
        metadata.pop("source", None)
    return metadata
