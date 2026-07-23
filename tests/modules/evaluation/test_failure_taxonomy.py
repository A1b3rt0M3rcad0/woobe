from __future__ import annotations

from modules.evaluation.application.failure_taxonomy import (
    canonical_judge_failure_code,
    judge_failure_policy,
    summarize_failures,
)


def test_historical_generic_judge_failure_is_classified_as_output_length() -> None:
    assert canonical_judge_failure_code(
        failure_code="judge_failed",
        failure_detail=(
            "LengthFinishReasonError: Could not parse response content as the "
            "length limit was reached"
        ),
        judge_status="failed",
        judge_error=None,
    ) == "judge_output_length_limit"


def test_model_call_error_is_classified_with_same_canonical_code() -> None:
    assert canonical_judge_failure_code(
        failure_code="judge_failed",
        failure_detail=None,
        judge_status="failed",
        judge_error=(
            "judge_output_length_limit: LengthFinishReasonError: "
            "completion_tokens=801 reasoning_tokens=800"
        ),
    ) == "judge_output_length_limit"


def test_null_score_type_error_is_classified_as_repairable_structured_response() -> None:
    code = canonical_judge_failure_code(
        failure_code="judge_failed",
        failure_detail=None,
        judge_status="failed",
        judge_error=(
            "judge_failed: TypeError: float() argument must be a string or a real "
            "number, not 'NoneType'"
        ),
    )

    assert code == "judge_invalid_json"
    assert judge_failure_policy(code)["retryable"] is True
    assert judge_failure_policy(code)["repairable"] is True


def test_invalid_confidence_after_repair_is_still_structured_contract_failure() -> None:
    code = canonical_judge_failure_code(
        failure_code="judge_failed",
        failure_detail=None,
        judge_status="failed",
        judge_error=(
            "judge_invalid_json: judge_failed: TypeError: float() argument must be a "
            "string or a real number, not 'NoneType'; governed_repair_failed: "
            "ValueError: Judge confidence is invalid"
        ),
    )

    assert code == "judge_invalid_json"
    assert judge_failure_policy(code)["repairable"] is True


def test_openrouter_402_is_terminal_insufficient_credits() -> None:
    code = canonical_judge_failure_code(
        failure_code="judge_failed",
        failure_detail=None,
        judge_status="failed",
        judge_error=(
            "APIStatusError: Error code: 402 - This request requires more credits, "
            "or fewer max_tokens. You requested up to 16384 tokens, but can only afford 1437."
        ),
    )

    assert code == "judge_insufficient_credits"
    assert judge_failure_policy(code) == {
        "retryable": False,
        "repairable": False,
        "scope": "run",
        "circuit_breaker": True,
        "recoverability": "user_action_required",
        "recommended_action": (
            "Add provider credits, reduce the Judge output budget or create a Suite "
            "Version with another Judge Model."
        ),
    }


def test_failure_summary_accepts_preserved_output_as_runtime_evidence() -> None:
    result = summarize_failures(
        [
            {
                "id": "trial-1",
                "status": "inconclusive",
                "failure_code": "judge_failed",
                "failure_detail": "length limit was reached",
                "metrics": {},
                "output": {"answer": "preserved"},
            }
        ],
        [
            {
                "trial_id": "trial-1",
                "status": "failed",
                "error": "LengthFinishReasonError: length limit was reached",
            }
        ],
    )

    assert result["primary"]["code"] == "judge_output_length_limit"
    assert result["primary"]["stage"] == "judge"
    assert result["primary"]["trial_ids"] == ["trial-1"]
