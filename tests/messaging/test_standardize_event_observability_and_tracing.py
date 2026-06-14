"""Tests for spec 108 — standardize event observability and tracing."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared.messaging.observability import (
    REQUIRED_LOG_FIELDS,
    REQUIRED_METRICS_NAMES,
    EventDirection,
    EventLogRecord,
    EventMetrics,
    EventObserver,
    EventStage,
    ObservabilityError,
    build_log_dict,
    compute_inbox_lag,
    compute_outbox_lag,
    propagate_trace,
    validate_log_record,
    validate_metrics,
)


class TestLogRecordValidation:
    """Log records must contain required fields."""

    def test_valid_log_record(self):
        record = {
            "event_id": "evt-001",
            "event_type": "agent.execution_requested.v1",
            "routing_key": "agent.execution.requested.v1",
            "correlation_id": "corr-001",
            "producer_module": "agent",
        }
        validate_log_record(record)

    def test_missing_required_field_raises(self):
        for field in REQUIRED_LOG_FIELDS:
            record = {
                "event_id": "evt-001",
                "event_type": "agent.execution_requested.v1",
                "routing_key": "agent.execution.requested.v1",
                "correlation_id": "corr-001",
                "producer_module": "agent",
            }
            record.pop(field)
            with pytest.raises(ObservabilityError):
                validate_log_record(record)

    def test_empty_event_id_raises(self):
        record = {
            "event_id": "",
            "event_type": "agent.execution_requested.v1",
            "routing_key": "agent.execution.requested.v1",
            "correlation_id": "corr-001",
            "producer_module": "agent",
        }
        with pytest.raises(ObservabilityError, match="event_id"):
            validate_log_record(record)

    def test_empty_event_type_raises(self):
        record = {
            "event_id": "evt-001",
            "event_type": "",
            "routing_key": "agent.execution.requested.v1",
            "correlation_id": "corr-001",
            "producer_module": "agent",
        }
        with pytest.raises(ObservabilityError, match="event_type"):
            validate_log_record(record)

    def test_empty_routing_key_raises(self):
        record = {
            "event_id": "evt-001",
            "event_type": "agent.execution_requested.v1",
            "routing_key": "",
            "correlation_id": "corr-001",
            "producer_module": "agent",
        }
        with pytest.raises(ObservabilityError, match="routing_key"):
            validate_log_record(record)

    def test_empty_correlation_id_raises(self):
        record = {
            "event_id": "evt-001",
            "event_type": "agent.execution_requested.v1",
            "routing_key": "agent.execution.requested.v1",
            "correlation_id": "",
            "producer_module": "agent",
        }
        with pytest.raises(ObservabilityError, match="correlation_id"):
            validate_log_record(record)

    def test_empty_producer_module_raises(self):
        record = {
            "event_id": "evt-001",
            "event_type": "agent.execution_requested.v1",
            "routing_key": "agent.execution.requested.v1",
            "correlation_id": "corr-001",
            "producer_module": "",
        }
        with pytest.raises(ObservabilityError, match="producer_module"):
            validate_log_record(record)


class TestMetricsValidation:
    """Metrics must contain required names."""

    def test_valid_metrics(self):
        metrics = {
            "events_published_total": 0,
            "events_publish_failures_total": 0,
            "events_retries_total": 0,
            "events_dead_letter_total": 0,
            "outbox_lag_seconds": 0.0,
            "inbox_lag_seconds": 0.0,
        }
        validate_metrics(metrics)

    def test_missing_metric_raises(self):
        for name in REQUIRED_METRICS_NAMES:
            metrics = {
                "events_published_total": 0,
                "events_publish_failures_total": 0,
                "events_retries_total": 0,
                "events_dead_letter_total": 0,
                "outbox_lag_seconds": 0.0,
                "inbox_lag_seconds": 0.0,
            }
            metrics.pop(name)
            with pytest.raises(ObservabilityError, match=name):
                validate_metrics(metrics)

    def test_non_numeric_metric_raises(self):
        metrics = {
            "events_published_total": "not-a-number",
            "events_publish_failures_total": 0,
            "events_retries_total": 0,
            "events_dead_letter_total": 0,
            "outbox_lag_seconds": 0.0,
            "inbox_lag_seconds": 0.0,
        }
        with pytest.raises(ObservabilityError, match="numeric"):
            validate_metrics(metrics)

    def test_negative_metric_raises(self):
        metrics = {
            "events_published_total": -1,
            "events_publish_failures_total": 0,
            "events_retries_total": 0,
            "events_dead_letter_total": 0,
            "outbox_lag_seconds": 0.0,
            "inbox_lag_seconds": 0.0,
        }
        with pytest.raises(ObservabilityError, match="non-negative"):
            validate_metrics(metrics)

    def test_required_metrics_names_contains_six(self):
        assert len(REQUIRED_METRICS_NAMES) == 6


class TestEventLogRecord:
    """EventLogRecord dataclass."""

    def test_default_values(self):
        record = EventLogRecord(
            event_id="evt-001",
            event_type="agent.execution_requested.v1",
            routing_key="agent.execution.requested.v1",
            correlation_id="corr-001",
            producer_module="agent",
            direction=EventDirection.PUBLISH,
            stage=EventStage.OUTBOX_PERSISTED,
        )
        assert record.event_id == "evt-001"
        assert record.causation_id is None
        assert record.error is None
        assert record.attempts == 0
        assert record.metadata == {}
        assert isinstance(record.timestamp, datetime)

    def test_with_optional_fields(self):
        record = EventLogRecord(
            event_id="evt-002",
            event_type="identity.user.created.v1",
            routing_key="identity.user.created.v1",
            correlation_id="corr-002",
            producer_module="identity",
            direction=EventDirection.CONSUME,
            stage=EventStage.INBOX_RECEIVED,
            causation_id="caus-001",
            consumer_module="agent",
            event_version=1,
            aggregate_type="user",
            aggregate_id="agg-001",
            error="timeout",
            attempts=3,
            metadata={"retry_count": 2},
        )
        assert record.causation_id == "caus-001"
        assert record.consumer_module == "agent"
        assert record.error == "timeout"
        assert record.attempts == 3


class TestEventMetrics:
    """EventMetrics dataclass."""

    def test_defaults_are_zero(self):
        metrics = EventMetrics()
        assert metrics.events_published_total == 0
        assert metrics.events_publish_failures_total == 0
        assert metrics.events_retries_total == 0
        assert metrics.events_dead_letter_total == 0
        assert metrics.outbox_lag_seconds == 0.0
        assert metrics.inbox_lag_seconds == 0.0

    def test_custom_values(self):
        metrics = EventMetrics(
            events_published_total=10,
            events_publish_failures_total=2,
            events_retries_total=5,
            events_dead_letter_total=1,
            outbox_lag_seconds=1.5,
            inbox_lag_seconds=3.2,
        )
        assert metrics.events_published_total == 10
        assert metrics.outbox_lag_seconds == 1.5


class TestBuildLogDict:
    """build_log_dict produces valid log records."""

    def test_build_log_dict(self):
        result = build_log_dict(
            event_id="evt-001",
            event_type="agent.execution_requested.v1",
            routing_key="agent.execution.requested.v1",
            correlation_id="corr-001",
            producer_module="agent",
            direction=EventDirection.PUBLISH,
            stage=EventStage.PUBLISHED,
        )
        assert result["event_id"] == "evt-001"
        assert result["direction"] == "publish"
        assert result["stage"] == "published"

    def test_built_record_validates(self):
        result = build_log_dict(
            event_id="evt-001",
            event_type="agent.execution_requested.v1",
            routing_key="agent.execution.requested.v1",
            correlation_id="corr-001",
            producer_module="agent",
            direction=EventDirection.PUBLISH,
            stage=EventStage.PUBLISHED,
        )
        validate_log_record(result)


class TestLagComputation:
    """Outbox and Inbox lag computation."""

    def test_outbox_lag_positive(self):
        persisted = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
        published = datetime(2026, 6, 14, 10, 0, 5, tzinfo=timezone.utc)
        assert compute_outbox_lag(persisted, published) == 5.0

    def test_outbox_lag_zero(self):
        now = datetime.now(timezone.utc)
        assert compute_outbox_lag(now, now) == 0.0

    def test_outbox_lag_negative_clamped(self):
        persisted = datetime(2026, 6, 14, 10, 0, 5, tzinfo=timezone.utc)
        published = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
        assert compute_outbox_lag(persisted, published) == 0.0

    def test_inbox_lag_positive(self):
        published = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
        processed = datetime(2026, 6, 14, 10, 0, 10, tzinfo=timezone.utc)
        assert compute_inbox_lag(published, processed) == 10.0


class TestTracePropagation:
    """Trace propagation via correlation/causation."""

    def test_propagate_trace_basic(self):
        trace = propagate_trace(correlation_id="corr-001")
        assert trace.correlation_id == "corr-001"
        assert trace.causation_id is None
        assert trace.trace_id is not None
        assert trace.span_id is not None

    def test_propagate_trace_with_causation(self):
        trace = propagate_trace(
            correlation_id="corr-002",
            causation_id="caus-001",
            trace_id="trace-001",
            parent_span_id="span-001",
        )
        assert trace.correlation_id == "corr-002"
        assert trace.causation_id == "caus-001"
        assert trace.trace_id == "trace-001"
        assert trace.span_id == "span-001"

    def test_empty_correlation_id_raises(self):
        with pytest.raises(ObservabilityError, match="correlation_id"):
            propagate_trace(correlation_id="")


class TestEventObserverProtocol:
    """EventObserver Protocol is runtime checkable."""

    def test_conforming_observer(self):
        class GoodObserver:
            def on_event_log(self, record: EventLogRecord) -> None:
                pass

            def on_event_metrics(self, metrics: EventMetrics) -> None:
                pass

        obs = GoodObserver()
        assert isinstance(obs, EventObserver)

    def test_non_conforming_observer(self):
        class BadObserver:
            pass

        obs = BadObserver()
        assert not isinstance(obs, EventObserver)

    def test_partial_observer_fails(self):
        class PartialObserver:
            def on_event_log(self, record: EventLogRecord) -> None:
                pass

        obs = PartialObserver()
        assert not isinstance(obs, EventObserver)


class TestEventDirectionAndStage:
    """Enum values are well-formed."""

    def test_direction_values(self):
        assert EventDirection.PUBLISH.value == "publish"
        assert EventDirection.CONSUME.value == "consume"

    def test_stage_values_are_lowercase(self):
        for stage in EventStage:
            assert stage.value == stage.value.lower()
            assert " " not in stage.value


class TestObservabilityIdempotency:
    """Validation is deterministic and repeatable."""

    def test_valid_log_record_validates_repeatedly(self):
        record = {
            "event_id": "evt-001",
            "event_type": "agent.execution_requested.v1",
            "routing_key": "agent.execution.requested.v1",
            "correlation_id": "corr-001",
            "producer_module": "agent",
        }
        for _ in range(10):
            validate_log_record(record)

    def test_valid_metrics_validates_repeatedly(self):
        metrics = {
            "events_published_total": 0,
            "events_publish_failures_total": 0,
            "events_retries_total": 0,
            "events_dead_letter_total": 0,
            "outbox_lag_seconds": 0.0,
            "inbox_lag_seconds": 0.0,
        }
        for _ in range(10):
            validate_metrics(metrics)
