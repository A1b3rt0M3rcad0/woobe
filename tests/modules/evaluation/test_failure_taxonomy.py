from __future__ import annotations

from modules.evaluation.application.failure_taxonomy import (
    canonical_judge_failure_code,
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
