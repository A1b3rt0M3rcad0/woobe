from __future__ import annotations

import pytest

from modules.evaluation.domain.contracts import (
    assess_expected_outcome,
    classify_runtime_failure,
    normalize_test_case,
    validate_suite_draft,
)
from shared.infra.errors import ValidationError


def test_expected_tool_failure_can_pass() -> None:
    assessment = assess_expected_outcome(
        case_type="expected_failure",
        expected_outcome={
            "type": "expected_failure",
            "allowed_failure_origins": ["tool"],
            "allowed_failure_stages": ["tool_execution"],
            "allowed_failure_codes": ["tool_timeout"],
        },
        observed_outcome={
            "type": "failure",
            "failure_origin": "tool",
            "failure_stage": "tool_execution",
            "failure_code": "tool_timeout",
        },
        answer=None,
    )

    assert assessment.passed is True
    assert assessment.score == 100


def test_platform_failure_can_never_pass() -> None:
    assessment = assess_expected_outcome(
        case_type="expected_failure",
        expected_outcome={
            "type": "expected_failure",
            "allowed_failure_stages": ["runtime"],
        },
        observed_outcome={
            "type": "failure",
            "failure_origin": "platform",
            "failure_stage": "runtime",
            "failure_code": "worker_unavailable",
        },
        answer=None,
    )

    assert assessment.passed is None
    assert assessment.status == "inconclusive"


def test_expected_failure_requires_observable_constraint() -> None:
    with pytest.raises(ValidationError):
        normalize_test_case(
            {
                "name": "Invalid failure contract",
                "case_type": "expected_failure",
                "message": "Trigger a failure",
                "expected_outcome": {"type": "expected_failure"},
            },
            position=1,
        )


def test_success_case_requires_observable_criteria() -> None:
    with pytest.raises(ValidationError):
        normalize_test_case(
            {
                "name": "No expected behavior",
                "case_type": "success",
                "message": "Hello",
            },
            position=1,
        )


def test_tool_timeout_is_normalized_to_stable_code() -> None:
    observed = classify_runtime_failure(
        RuntimeError("Tool invoice_lookup timed out after 5000ms")
    )

    assert observed["failure_origin"] == "tool"
    assert observed["failure_stage"] == "tool_execution"
    assert observed["failure_code"] == "tool_timeout"


def test_database_failure_is_platform_persistence_error() -> None:
    observed = classify_runtime_failure(
        RuntimeError("Database transaction commit failed")
    )

    assert observed["failure_origin"] == "platform"
    assert observed["failure_stage"] == "persistence"
    assert observed["failure_code"] == "persistence_error"


def test_suite_validation_warns_without_negative_cases() -> None:
    result = validate_suite_draft(
        {
            "schema_version": 1,
            "cases": [
                {
                    "name": "Happy path",
                    "case_type": "success",
                    "message": "Hello",
                    "expected_contract": {"semantic_criteria": ["Respond clearly"]},
                }
            ],
        }
    )

    assert result["valid"] is True
    assert result["case_count"] == 1
    assert any(item["code"] == "no_negative_cases" for item in result["warnings"])
