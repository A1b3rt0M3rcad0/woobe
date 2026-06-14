"""Tests for spec 105 — standardize dead letter policy."""
from __future__ import annotations

from datetime import datetime

import pytest

from shared.messaging.dead_letter_policy import (
    DLQ_SUFFIX,
    DLX_SUFFIX,
    DeadLetterReason,
    create_dead_letter_record,
    dead_letter_headers,
    compute_dlq_name,
    compute_dlx_name,
    is_dead_letter_exchange_name,
    is_dead_letter_queue_name,
    verify_dlq_headers,
)


class TestNamingConventions:
    """DLQ/DLX naming convention tests."""

    def test_dlq_name_suffix(self):
        assert compute_dlq_name("agent.inbox") == "agent.inbox.dlq"
        assert compute_dlq_name("billing.outbox") == "billing.outbox.dlq"

    def test_dlx_name_suffix(self):
        assert compute_dlx_name("agent.events") == "agent.events.dlx"
        assert compute_dlx_name("billing.events") == "billing.events.dlx"

    def test_empty_queue_name_raises(self):
        with pytest.raises(ValueError):
            compute_dlq_name("")

    def test_empty_exchange_name_raises(self):
        with pytest.raises(ValueError):
            compute_dlx_name("")

    def test_is_dead_letter_queue_name(self):
        assert is_dead_letter_queue_name("agent.inbox.dlq") is True
        assert is_dead_letter_queue_name("agent.inbox") is False
        assert is_dead_letter_queue_name("something.dlx") is False

    def test_is_dead_letter_exchange_name(self):
        assert is_dead_letter_exchange_name("agent.events.dlx") is True
        assert is_dead_letter_exchange_name("agent.events") is False
        assert is_dead_letter_exchange_name("something.dlq") is False


class TestDeadLetterReasons:
    """All DeadLetterReason values."""

    def test_all_reasons_defined(self):
        reasons = list(DeadLetterReason)
        assert DeadLetterReason.MAX_RETRIES_EXCEEDED in reasons
        assert DeadLetterReason.PERMANENT_ERROR in reasons
        assert DeadLetterReason.INCOMPATIBLE_VERSION in reasons
        assert DeadLetterReason.INVALID_SCHEMA in reasons
        assert DeadLetterReason.REJECTED_BY_POLICY in reasons

    def test_reason_values_are_lowercase_identifiers(self):
        for reason in DeadLetterReason:
            assert reason.value == reason.value.lower()
            assert " " not in reason.value


class TestDeadLetterHeaders:
    """Dead letter headers contain required audit info."""

    def test_headers_contain_all_required_fields(self):
        headers = dead_letter_headers(
            reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
            original_routing_key="agent.execution.requested.v1",
            original_producer_module="agent",
            attempts=5,
            error="ConnectionTimeout",
        )
        assert verify_dlq_headers(headers)

    def test_headers_for_each_reason(self):
        for reason in DeadLetterReason:
            headers = dead_letter_headers(
                reason=reason,
                original_routing_key="test.key.v1",
                original_producer_module="test",
                attempts=1,
                error="test error",
            )
            assert verify_dlq_headers(headers)

    def test_missing_header_field_fails_verification(self):
        headers = {"x-death-reason": "permanent_error"}
        assert not verify_dlq_headers(headers)

    def test_empty_headers_fails_verification(self):
        assert not verify_dlq_headers({})


class TestCreateDeadLetterRecord:
    """DeadLetterRecord preserves audit metadata."""

    def test_create_record_with_all_fields(self):
        record = create_dead_letter_record(
            reason=DeadLetterReason.INCOMPATIBLE_VERSION,
            original_routing_key="agent.v2.event.v1",
            original_producer_module="agent",
            original_payload={"key": "value"},
            attempts=5,
            error="Version mismatch",
        )
        assert record.reason == DeadLetterReason.INCOMPATIBLE_VERSION
        assert record.original_routing_key == "agent.v2.event.v1"
        assert record.original_producer_module == "agent"
        assert record.original_payload == {"key": "value"}
        assert record.attempts == 5
        assert record.error == "Version mismatch"
        assert verify_dlq_headers(record.headers)

    def test_create_record_defaults(self):
        record = create_dead_letter_record(
            reason=DeadLetterReason.PERMANENT_ERROR,
            original_routing_key="test.key",
            original_producer_module="test",
        )
        assert record.attempts == 0
        assert record.error == ""
        assert record.original_payload == {}

    def test_record_timestamp_set(self):
        record = create_dead_letter_record(
            reason=DeadLetterReason.REJECTED_BY_POLICY,
            original_routing_key="key",
            original_producer_module="mod",
        )
        assert record.occurred_at is not None
        assert isinstance(record.occurred_at, datetime)


class TestDeadLetterAuditPreservation:
    """DLQ does not replace Inbox 'dead'; both allow audit."""

    def test_dlq_suffix_constant(self):
        assert DLQ_SUFFIX == ".dlq"
        assert DLX_SUFFIX == ".dlx"

    def test_inbox_dead_status_is_separate_from_dlq(self):
        from shared.messaging.idempotency_contracts import DUPLICATE_OUTCOMES
        from shared.messaging.retry_policy import TERMINAL_STATUSES

        assert "dead" in TERMINAL_STATUSES
        assert "dead" not in DUPLICATE_OUTCOMES

    def test_dead_letter_reasons_do_not_overlap_with_domain_statuses(self):
        reason_values = {r.value for r in DeadLetterReason}
        assert "processed" not in reason_values
        assert "pending" not in reason_values
        assert "retryable" not in reason_values
