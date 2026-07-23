from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from modules.evaluation.infra.judge import _normalize_judgment
from modules.evaluation.infra.runtime_safe_judge import (
    canonicalize_repair_payload,
    is_judge_contract_error,
    is_null_score_contract_error,
    sanitize_judge_config,
)
from modules.evaluation.infra.workers.run_judge_worker import effective_suite_for_run


def test_null_score_type_error_is_recognized_as_structured_contract_failure() -> None:
    assert is_null_score_contract_error(
        "judge_failed: TypeError: float() argument must be a string or a real number, not 'NoneType'"
    ) is True
    assert is_judge_contract_error(
        "judge_failed: TypeError: float() argument must be a string or a real number, not 'NoneType'"
    ) is True


def test_invalid_confidence_is_recognized_as_structured_contract_failure() -> None:
    assert is_judge_contract_error(
        "governed_repair_failed: ValueError: Judge confidence is invalid"
    ) is True


def test_explicit_null_optional_judge_settings_fall_back_to_defaults() -> None:
    assert sanitize_judge_config(
        {
            "temperature": None,
            "timeout_seconds": None,
            "maximum_cost_usd": None,
            "max_tokens": 1200,
            "reasoning_policy": "provider_default",
        }
    ) == {
        "max_tokens": 1200,
        "reasoning_policy": "provider_default",
    }


def test_repair_payload_normalizes_numeric_confidence_and_string_score() -> None:
    payload, coercions = canonicalize_repair_payload(
        {
            "status": "pass",
            "score": "55.6/100",
            "confidence": 0.82,
            "dimensions": {"correctness": "61.5"},
            "criteria": [],
            "failures": [],
            "summary": "Usable answer",
        }
    )

    assert payload["status"] == "passed"
    assert payload["score"] == 55.6
    assert payload["confidence"] == "high"
    assert payload["dimensions"] == {"correctness": 61.5}
    assert coercions
    assert _normalize_judgment(payload)["score"] == 55.6


def test_repair_payload_normalizes_provider_specific_confidence_labels() -> None:
    high, _ = canonicalize_repair_payload(
        {"status": "failed", "score": 20, "confidence": "very high"}
    )
    medium, _ = canonicalize_repair_payload(
        {"status": "failed", "score": 20, "confidence": "moderate"}
    )
    unknown, coercions = canonicalize_repair_payload(
        {"status": "failed", "score": 20, "confidence": "provider-specific"}
    )

    assert high["confidence"] == "high"
    assert medium["confidence"] == "medium"
    assert unknown["confidence"] == "medium"
    assert any("medium_default" in item for item in coercions)
    _normalize_judgment(high)
    _normalize_judgment(medium)
    _normalize_judgment(unknown)


def test_repair_payload_recovers_null_score_from_terminal_verdict() -> None:
    passed, _ = canonicalize_repair_payload(
        {"status": "passed", "score": None, "confidence": "high"}
    )
    failed, _ = canonicalize_repair_payload(
        {"status": "failed", "score": None, "confidence": "low"}
    )

    assert passed["score"] == 100.0
    assert failed["score"] == 0.0
    _normalize_judgment(passed)
    _normalize_judgment(failed)


def test_effective_suite_uses_judge_frozen_on_run_without_mutating_suite() -> None:
    suite_judge_id = uuid4()
    run_judge_id = uuid4()
    suite = SimpleNamespace(
        judge_provider_model_id=suite_judge_id,
        judge_config={"max_tokens": 1200},
        rubric={"judge_weight": 4},
        deterministic_checks={"enabled": True},
    )
    run = SimpleNamespace(
        execution_policy={
            "judge_protocol": {
                "source": "run_override",
                "judge_provider_model_id": str(run_judge_id),
                "normalized_judge_config": {
                    "max_tokens": 2048,
                    "attempts": 3,
                },
            }
        }
    )

    effective = effective_suite_for_run(run, suite)

    assert effective.judge_provider_model_id == run_judge_id
    assert effective.judge_config == {"max_tokens": 2048, "attempts": 3}
    assert effective.rubric == suite.rubric
    assert effective.deterministic_checks == suite.deterministic_checks
    assert suite.judge_provider_model_id == suite_judge_id
    assert suite.judge_config == {"max_tokens": 1200}
