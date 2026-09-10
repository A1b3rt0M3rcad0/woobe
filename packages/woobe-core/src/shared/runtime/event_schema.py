from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from shared.contracts.run_event_buffer import BufferedRunEvent
from shared.contracts.run_event_journal import DurableRunEvent

RUN_EVENT_SCHEMA_VERSION = 1
EVENT_JOURNAL_STORAGE_VERSION = "event_journal_v1"
LEGACY_STORAGE_VERSION = "legacy_v1"

TERMINAL_EVENT_TYPES = {
    "run.completed": "completed",
    "run.failed": "failed",
    "run.cancelled": "cancelled",
    "run.timed_out": "timed_out",
    "run.uncertain": "uncertain",
}

CHECKPOINT_EVENT_TYPE = "execution.checkpoint"

DURABLE_EVENT_TYPES = {
    "run.attempt.started",
    "run.attempt.interrupted",
    "execution.started",
    "context.snapshot.materialized",
    "model.invocation.started",
    "model.invocation.completed",
    "model.invocation.failed",
    "knowledge.retrieval.completed",
    "tool.call.started",
    "tool.call.completed",
    "tool.call.failed",
    "fallback.triggered",
    "output.delta.batch",
    "output.retracted",
    "agent.invocation.started",
    "agent.invocation.completed",
    "agent.invocation.failed",
    "agent.invocation.cancelled",
    "delegation.started",
    "delegation.completed",
    "delegation.failed",
    "delegation.skipped",
    CHECKPOINT_EVENT_TYPE,
    *TERMINAL_EVENT_TYPES.keys(),
}

_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "decrypted_secret",
    "credential_secret",
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_run_event_value(value: Any) -> Any:
    """Remove credential material before Redis/Mongo persistence.

    Identifier/provenance fields such as ``provider_credential_id`` remain valid.
    Hidden model reasoning is never emitted by callers and this sanitizer is a final
    defensive boundary rather than a substitute for correct event contracts.
    """

    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key.strip().lower() in _SENSITIVE_KEYS:
                continue
            clean[key] = sanitize_run_event_value(raw_value)
        return clean
    if isinstance(value, list):
        return [sanitize_run_event_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_run_event_value(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return sanitize_run_event_value(value.model_dump())
    return str(value)


def validate_event_type(event_type: str) -> str:
    normalized = event_type.strip()
    if normalized not in DURABLE_EVENT_TYPES:
        raise ValueError(f"Unsupported durable Run event type: {event_type}")
    return normalized


def buffered_to_durable(event: BufferedRunEvent) -> DurableRunEvent:
    validate_event_type(event.event_type)
    return DurableRunEvent(
        run_id=event.run_id,
        run_kind=event.run_kind,
        sequence=event.sequence,
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        schema_version=event.schema_version,
        storage_version=event.storage_version,
        metadata=sanitize_run_event_value(deepcopy(event.metadata)),
        payload=sanitize_run_event_value(deepcopy(event.payload)),
    )


def new_event_id() -> str:
    return str(uuid4())
