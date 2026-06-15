"""Integration tests for spec 094 — standardize idempotency, retry and dead letter.

Verifies the shared idempotency, retry policy, and dead letter contracts.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared.messaging.dead_letter_policy import (
    DLQ_SUFFIX,
    DLX_SUFFIX,
    DeadLetterReason,
    DeadLetterRecord,
    compute_dlq_name,
    compute_dlx_name,
    create_dead_letter_record,
    dead_letter_headers,
    is_dead_letter_queue_name,
    is_dead_letter_exchange_name,
    verify_dlq_headers,
)
from shared.messaging.idempotency_contracts import (
    IDEMPOTENCY_KEY_MIN_LENGTH,
    IDEMPOTENCY_KEY_MAX_LENGTH,
    IdempotencyKeyValidationError,
    assert_idempotency_constraints,
    is_allowed_duplicate_outcome,
    is_allowed_duplicate_outbox_outcome,
    validate_idempotency_key,
)
from shared.messaging.retry_policy import (
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_DELAY_SECONDS,
    PERMANENT_ERROR_TYPES,
    RETRYABLE_STATUSES,
    TERMINAL_STATUSES,
    TRANSIENT_ERROR_TYPES,
    RetryClassification,
    classify_error,
    compute_backoff_delay,
    compute_next_available_at,
    is_retryable_status,
    is_terminal_status,
    should_retry,
)


# ── Idempotency ──


def test_idempotency_key_min_length():
    assert IDEMPOTENCY_KEY_MIN_LENGTH >= 1


def test_idempotency_key_max_length():
    assert IDEMPOTENCY_KEY_MAX_LENGTH >= 1


def test_validate_idempotency_key_valid():
    validate_idempotency_key("abc-123-def")


def test_validate_idempotency_key_empty_raises():
    with pytest.raises(IdempotencyKeyValidationError):
        validate_idempotency_key("")


def test_validate_idempotency_key_too_long_raises():
    long_key = "x" * (IDEMPOTENCY_KEY_MAX_LENGTH + 1)
    with pytest.raises(IdempotencyKeyValidationError):
        validate_idempotency_key(long_key)


def test_assert_idempotency_constraints_raises_for_non_sqlalchemy():
    """Non-SQLAlchemy class raises IdempotencyKeyValidationError."""
    with pytest.raises((IdempotencyKeyValidationError, AttributeError)):
        assert_idempotency_constraints(str)


def test_is_allowed_duplicate_outcome():
    assert is_allowed_duplicate_outcome("processed")
    assert is_allowed_duplicate_outcome("ignored")
    assert not is_allowed_duplicate_outcome("pending")


def test_is_allowed_duplicate_outbox_outcome():
    assert is_allowed_duplicate_outbox_outcome("published")
    assert is_allowed_duplicate_outbox_outcome("duplicate")
    assert not is_allowed_duplicate_outbox_outcome("pending")


# ── Retry Policy ──


def test_default_max_attempts():
    assert DEFAULT_MAX_ATTEMPTS >= 3


def test_default_base_delay():
    assert DEFAULT_BASE_DELAY_SECONDS > 0


def test_default_max_delay():
    assert DEFAULT_MAX_DELAY_SECONDS > DEFAULT_BASE_DELAY_SECONDS


def test_retry_classification_values():
    assert RetryClassification.TRANSIENT.value == "transient"
    assert RetryClassification.PERMANENT.value == "permanent"


def test_classify_error_defaults_to_transient():
    assert classify_error("UnknownError") == RetryClassification.TRANSIENT


def test_classify_error_connection_error_as_transient():
    assert classify_error("ConnectionError") == RetryClassification.TRANSIENT


def test_classify_error_permanent():
    assert classify_error("ValidationError") == RetryClassification.PERMANENT
    assert classify_error("InvalidPayloadError") == RetryClassification.PERMANENT


def test_transient_error_types_not_empty():
    assert len(TRANSIENT_ERROR_TYPES) > 0


def test_permanent_error_types_not_empty():
    assert len(PERMANENT_ERROR_TYPES) > 0


def test_compute_backoff_delay_zero_attempts():
    delay = compute_backoff_delay(0)
    assert delay > 0


def test_compute_backoff_delay_increases_with_attempts():
    d1 = compute_backoff_delay(1, jitter_factor=0.0)
    d2 = compute_backoff_delay(2, jitter_factor=0.0)
    assert d2 >= d1


def test_compute_backoff_delay_capped():
    delay = compute_backoff_delay(100, max_delay_seconds=10.0, jitter_factor=0.0)
    assert delay <= 10.0


def test_compute_next_available_at_returns_future():
    future = compute_next_available_at(1)
    assert future > datetime.now(timezone.utc)


def test_should_retry_within_limit():
    assert should_retry(attempts=0, max_attempts=5) is True
    assert should_retry(attempts=4, max_attempts=5) is True


def test_should_retry_exhausted():
    assert should_retry(attempts=5, max_attempts=5) is False
    assert should_retry(attempts=6, max_attempts=5) is False


def test_should_retry_permanent():
    assert should_retry(attempts=0, error="ValidationError") is False


def test_retryable_statuses():
    assert is_retryable_status("pending")
    assert is_retryable_status("retryable")
    assert not is_retryable_status("published")


def test_terminal_statuses():
    assert is_terminal_status("published")
    assert is_terminal_status("processed")
    assert is_terminal_status("dead")
    assert not is_terminal_status("pending")


def test_retryable_statuses_not_empty():
    assert len(RETRYABLE_STATUSES) > 0


def test_terminal_statuses_not_empty():
    assert len(TERMINAL_STATUSES) > 0


# ── Dead Letter ──


def test_dlq_suffix():
    assert DLQ_SUFFIX == ".dlq"


def test_dlx_suffix():
    assert DLX_SUFFIX == ".dlx"


def test_compute_dlq_name():
    assert compute_dlq_name("agent.billing-events") == "agent.billing-events.dlq"


def test_compute_dlx_name():
    assert compute_dlx_name("domain.events") == "domain.events.dlx"


def test_dead_letter_reason_values():
    assert DeadLetterReason.MAX_RETRIES_EXCEEDED.value == "max_retries_exceeded"
    assert DeadLetterReason.PERMANENT_ERROR.value == "permanent_error"


def test_dead_letter_headers_contains_required_keys():
    headers = dead_letter_headers(
        reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
        original_routing_key="agent.execution.requested.v1",
        original_producer_module="agent",
        attempts=3,
        error="timeout",
    )
    assert verify_dlq_headers(headers)


def test_create_dead_letter_record():
    record = create_dead_letter_record(
        reason=DeadLetterReason.PERMANENT_ERROR,
        original_routing_key="billing.plan.created.v1",
        original_producer_module="billing",
        original_payload={"plan_id": "abc"},
        attempts=5,
        error="invalid_schema",
    )
    assert isinstance(record, DeadLetterRecord)
    assert record.reason == DeadLetterReason.PERMANENT_ERROR
    assert record.attempts == 5


def test_is_dead_letter_queue_name():
    assert is_dead_letter_queue_name("agent.billing-events.dlq")
    assert not is_dead_letter_queue_name("agent.billing-events")


def test_is_dead_letter_exchange_name():
    assert is_dead_letter_exchange_name("domain.events.dlx")
    assert not is_dead_letter_exchange_name("domain.events")
