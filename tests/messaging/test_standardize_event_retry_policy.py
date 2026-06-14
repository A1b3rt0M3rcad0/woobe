"""Tests for spec 104 — standardize event retry policy."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared.messaging.retry_policy import (
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_DELAY_SECONDS,
    PERMANENT_ERROR_TYPES,
    TRANSIENT_ERROR_TYPES,
    RetryClassification,
    RetryState,
    classify_error,
    compute_backoff_delay,
    compute_next_available_at,
    is_retryable_status,
    is_terminal_status,
    should_retry,
)


class TestRetryClassification:
    """Transient and permanent error classification."""

    def test_transient_errors_classified_correctly(self):
        transient_errors = [
            "ConnectionError: postgres host unreachable",
            "ConnectionRefusedError: broker down",
            "TimeoutError: operation timed out",
            "ConnectionResetError: peer reset",
        ]
        for error in transient_errors:
            assert classify_error(error) == RetryClassification.TRANSIENT, error

    def test_permanent_errors_classified_correctly(self):
        permanent_errors = [
            "ValidationError: invalid payload",
            "SchemaError: unknown field",
            "IncompatibleVersionError: v3 unsupported",
            "MissingHandlerError: no handler for event",
            "BusinessRuleViolation: quota exceeded",
        ]
        for error in permanent_errors:
            assert classify_error(error) == RetryClassification.PERMANENT, error

    def test_unknown_errors_default_to_transient(self):
        assert classify_error("SomeUnknownError message") == RetryClassification.TRANSIENT

    def test_transient_error_types_frozenset_not_empty(self):
        assert len(TRANSIENT_ERROR_TYPES) > 0

    def test_permanent_error_types_frozenset_not_empty(self):
        assert len(PERMANENT_ERROR_TYPES) > 0


class TestBackoffComputation:
    """Exponential backoff with jitter."""

    def test_first_attempt_uses_base_delay(self):
        delay = compute_backoff_delay(attempts=1, jitter_factor=0.0)
        assert delay == pytest.approx(DEFAULT_BASE_DELAY_SECONDS)

    def test_backoff_increases_with_attempts(self):
        d1 = compute_backoff_delay(attempts=1, jitter_factor=0.0)
        d2 = compute_backoff_delay(attempts=2, jitter_factor=0.0)
        d3 = compute_backoff_delay(attempts=3, jitter_factor=0.0)
        assert d3 > d2 > d1

    def test_backoff_capped_at_max_delay(self):
        delay = compute_backoff_delay(attempts=100, jitter_factor=0.0)
        assert delay <= DEFAULT_MAX_DELAY_SECONDS

    def test_backoff_with_jitter_produces_variation(self):
        delays = [compute_backoff_delay(attempts=3) for _ in range(50)]
        distinct = len(set(round(d, 2) for d in delays))
        assert distinct > 1, "Jitter should produce variation"

    def test_zero_attempts_treated_as_one(self):
        delay = compute_backoff_delay(attempts=0, jitter_factor=0.0)
        assert delay == pytest.approx(DEFAULT_BASE_DELAY_SECONDS)

    def test_negative_attempts_treated_as_one(self):
        delay = compute_backoff_delay(attempts=-5, jitter_factor=0.0)
        assert delay == pytest.approx(DEFAULT_BASE_DELAY_SECONDS)


class TestNextAvailableAt:
    """Available_at calculation for scheduling retries."""

    def test_compute_next_available_at_is_future(self):
        now = datetime.now(timezone.utc)
        next_at = compute_next_available_at(attempts=1)
        assert next_at > now

    def test_subsequent_attempt_has_later_available_at(self):
        a1 = compute_next_available_at(attempts=1, jitter_factor=0.0)
        a2 = compute_next_available_at(attempts=2, jitter_factor=0.0)
        assert a2 > a1


class TestShouldRetry:
    """Retry decisions based on attempts and error classification."""

    def test_should_retry_below_max_attempts(self):
        assert should_retry(attempts=0, max_attempts=5) is True
        assert should_retry(attempts=4, max_attempts=5) is True

    def test_should_not_retry_at_max_attempts(self):
        assert should_retry(attempts=5, max_attempts=5) is False
        assert should_retry(attempts=10, max_attempts=5) is False

    def test_should_not_retry_permanent_errors(self):
        assert should_retry(
            attempts=0,
            max_attempts=5,
            classification=RetryClassification.PERMANENT,
        ) is False

    def test_should_not_retry_permanent_error_by_string(self):
        assert should_retry(
            attempts=0,
            max_attempts=5,
            error="SchemaError: invalid envelope",
        ) is False

    def test_default_max_attempts_is_5(self):
        assert DEFAULT_MAX_ATTEMPTS == 5


class TestStatusClassifications:
    """Retryable and terminal status sets."""

    def test_pending_is_retryable(self):
        assert is_retryable_status("pending")

    def test_retryable_is_retryable(self):
        assert is_retryable_status("retryable")

    def test_published_is_terminal(self):
        assert is_terminal_status("published")

    def test_processed_is_terminal(self):
        assert is_terminal_status("processed")

    def test_dead_is_terminal(self):
        assert is_terminal_status("dead")

    def test_ignored_is_terminal(self):
        assert is_terminal_status("ignored")

    def test_unknown_status_is_not_retryable(self):
        assert not is_retryable_status("unknown")

    def test_unknown_status_is_not_terminal(self):
        assert not is_terminal_status("unknown")


class TestRetryStateDataclass:
    """RetryState tracks attempts and timing."""

    def test_default_retry_state(self):
        state = RetryState()
        assert state.attempts == 0
        assert state.max_attempts == DEFAULT_MAX_ATTEMPTS
        assert state.last_error is None
        assert state.available_at is None

    def test_retry_state_custom_values(self):
        state = RetryState(
            attempts=3,
            max_attempts=10,
            base_delay_seconds=2.0,
            max_delay_seconds=600.0,
            last_error="TimeoutError",
        )
        assert state.attempts == 3
        assert state.max_attempts == 10
        assert state.base_delay_seconds == 2.0
        assert state.max_delay_seconds == 600.0
        assert state.last_error == "TimeoutError"
