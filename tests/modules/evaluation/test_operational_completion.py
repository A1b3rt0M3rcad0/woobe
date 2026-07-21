from __future__ import annotations

from uuid import uuid4

from modules.evaluation.application.completed_service import (
    _decode_cursor,
    _encode_cursor,
)
from modules.evaluation.application.durable_authoring import (
    _draft_uses_tools,
    _split_coverage,
)
from modules.evaluation.domain.enums import EvaluationTrialStatus


def test_authoring_batches_never_exceed_ten_cases() -> None:
    batches = _split_coverage(
        50,
        {
            "core_behavior": 12,
            "edge_cases": 8,
            "tools": 8,
            "knowledge": 6,
            "security_refusal": 6,
            "output_contract": 5,
            "error_handling": 5,
        },
    )

    assert len(batches) == 5
    assert all(sum(batch.values()) <= 10 for batch in batches)
    assert sum(sum(batch.values()) for batch in batches) == 50


def test_authoring_batch_distribution_preserves_requested_coverage() -> None:
    requested = {
        "core_behavior": 5,
        "tools": 4,
        "error_handling": 4,
        "security_refusal": 2,
    }
    batches = _split_coverage(15, requested)
    merged: dict[str, int] = {}
    for batch in batches:
        for key, value in batch.items():
            merged[key] = merged.get(key, 0) + value

    assert merged == requested


def test_draft_with_concrete_tool_requires_target_validation() -> None:
    assert _draft_uses_tools(
        {
            "schema_version": 1,
            "cases": [
                {
                    "name": "Tool case",
                    "message": "Find the invoice",
                    "expected_contract": {
                        "tools": {"required": ["invoice_lookup"]}
                    },
                }
            ],
        }
    ) is True


def test_semantic_only_draft_can_remain_generic() -> None:
    assert _draft_uses_tools(
        {
            "schema_version": 1,
            "cases": [
                {
                    "name": "Semantic case",
                    "message": "Explain the invoice status",
                    "expected_contract": {
                        "semantic_criteria": ["Do not invent a payment status"]
                    },
                }
            ],
        }
    ) is False


def test_cursor_roundtrip_preserves_timestamp_and_id() -> None:
    from datetime import datetime, timezone

    created_at = datetime(2026, 7, 21, 12, 30, tzinfo=timezone.utc)
    row_id = uuid4()

    decoded = _decode_cursor(_encode_cursor(created_at, row_id))

    assert decoded == (created_at, row_id)


def test_cancelled_trial_is_a_first_class_status() -> None:
    assert EvaluationTrialStatus.CANCELLED.value == "cancelled"
