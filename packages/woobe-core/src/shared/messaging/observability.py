"""Standardized event observability and tracing contracts.

Defines log field requirements, trace propagation, and minimum metric
contracts applicable to all modules.

Rules:
 1. Logs must contain event_id, event_type, routing_key, correlation_id,
    causation_id, producer_module, and consumer_module when available.
 2. Minimum metrics: events published, failures, retries, DLQ events,
    Outbox lag, Inbox lag.
 3. Tracing must propagate correlation and causation without creating
    direct dependencies between domain modules.
 4. Observability hooks are generic and must not depend on any module's
    domain knowledge.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


REQUIRED_LOG_FIELDS: frozenset[str] = frozenset(
    [
        "event_id",
        "event_type",
        "routing_key",
        "correlation_id",
        "producer_module",
    ]
)

OPTIONAL_LOG_FIELDS: frozenset[str] = frozenset(
    [
        "causation_id",
        "consumer_module",
        "event_version",
        "aggregate_type",
        "aggregate_id",
    ]
)

REQUIRED_METRICS_NAMES: frozenset[str] = frozenset(
    [
        "events_published_total",
        "events_publish_failures_total",
        "events_retries_total",
        "events_dead_letter_total",
        "outbox_lag_seconds",
        "inbox_lag_seconds",
    ]
)


class EventDirection(str, enum.Enum):
    PUBLISH = "publish"
    CONSUME = "consume"


class EventStage(str, enum.Enum):
    OUTBOX_PERSISTED = "outbox_persisted"
    DISPATCH_ATTEMPT = "dispatch_attempt"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
    RETRY = "retry"
    DEAD_LETTERED = "dead_lettered"
    INBOX_RECEIVED = "inbox_received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    PROCESS_FAILED = "process_failed"


class ObservabilityError(ValueError):
    pass


@dataclass
class TraceContext:
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


@dataclass
class EventLogRecord:
    event_id: str
    event_type: str
    routing_key: str
    correlation_id: str
    producer_module: str
    direction: EventDirection
    stage: EventStage
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    causation_id: str | None = None
    consumer_module: str | None = None
    event_version: int | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    error: str | None = None
    attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventMetrics:
    events_published_total: int = 0
    events_publish_failures_total: int = 0
    events_retries_total: int = 0
    events_dead_letter_total: int = 0
    outbox_lag_seconds: float = 0.0
    inbox_lag_seconds: float = 0.0


@runtime_checkable
class EventObserver(Protocol):
    def on_event_log(self, record: EventLogRecord) -> None: ...

    def on_event_metrics(self, metrics: EventMetrics) -> None: ...


def validate_log_record(record: dict[str, Any]) -> None:
    missing = REQUIRED_LOG_FIELDS - set(record.keys())
    if missing:
        raise ObservabilityError(
            f"Missing required log fields: {sorted(missing)}"
        )

    event_id = record.get("event_id")
    if not event_id:
        raise ObservabilityError("event_id must be non-empty")

    event_type = record.get("event_type", "")
    if not event_type or not isinstance(event_type, str):
        raise ObservabilityError("event_type must be a non-empty string")

    routing_key = record.get("routing_key", "")
    if not routing_key or not isinstance(routing_key, str):
        raise ObservabilityError("routing_key must be a non-empty string")

    correlation_id = record.get("correlation_id")
    if not correlation_id:
        raise ObservabilityError("correlation_id must be non-empty")

    producer_module = record.get("producer_module", "")
    if not producer_module or not isinstance(producer_module, str):
        raise ObservabilityError("producer_module must be a non-empty string")


def validate_metrics(metrics: dict[str, Any]) -> None:
    for name in REQUIRED_METRICS_NAMES:
        if name not in metrics:
            raise ObservabilityError(
                f"Missing required metric: {name}"
            )
        value = metrics[name]
        if not isinstance(value, (int, float)):
            raise ObservabilityError(
                f"Metric {name} must be numeric, got: {type(value).__name__}"
            )
        if value < 0:
            raise ObservabilityError(
                f"Metric {name} must be non-negative, got: {value}"
            )


def build_log_dict(
    event_id: str,
    event_type: str,
    routing_key: str,
    correlation_id: str,
    producer_module: str,
    direction: EventDirection,
    stage: EventStage,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "routing_key": routing_key,
        "correlation_id": correlation_id,
        "producer_module": producer_module,
        "direction": direction.value,
        "stage": stage.value,
    }
    return result


def compute_outbox_lag(
    persisted_at: datetime,
    published_at: datetime,
) -> float:
    delta = published_at - persisted_at
    return max(0.0, delta.total_seconds())


def compute_inbox_lag(
    published_at: datetime,
    processed_at: datetime,
) -> float:
    delta = processed_at - published_at
    return max(0.0, delta.total_seconds())


def propagate_trace(
    correlation_id: str,
    causation_id: str | None = None,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> TraceContext:
    if not correlation_id:
        raise ObservabilityError("correlation_id must not be empty")
    import uuid as _uuid
    return TraceContext(
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=trace_id or str(_uuid.uuid4()),
        span_id=parent_span_id or str(_uuid.uuid4()),
    )
