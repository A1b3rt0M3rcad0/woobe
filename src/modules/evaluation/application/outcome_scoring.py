from __future__ import annotations

from typing import Any

from modules.evaluation.application.scoring import DeterministicCheck
from modules.evaluation.domain.contracts import assess_expected_outcome


def evaluate_outcome_check(
    *,
    case_type: str,
    expected_contract: dict[str, Any] | None,
    output: dict[str, Any],
    metrics: dict[str, Any],
) -> DeterministicCheck:
    contract = expected_contract or {}
    expected_outcome = contract.get("expected_outcome")
    observed = metrics.get("observed_outcome")
    if not isinstance(observed, dict):
        observed = output.get("observed_outcome")
    if not isinstance(observed, dict):
        observed = {"type": "success"}
    assessment = assess_expected_outcome(
        case_type=case_type,
        expected_outcome=expected_outcome if isinstance(expected_outcome, dict) else None,
        observed_outcome=observed,
        answer=output.get("answer") if isinstance(output.get("answer"), str) else None,
    )
    status = assessment.status
    if status == "inconclusive":
        score = None
    else:
        score = assessment.score
    return DeterministicCheck(
        key="expected_outcome",
        dimension="outcome",
        status=status,
        score=score,
        blocking=assessment.blocking,
        reason=assessment.reason,
        evidence=assessment.evidence,
        weight=4.0,
    )


def outcome_is_platform_failure(metrics: dict[str, Any]) -> bool:
    observed = metrics.get("observed_outcome")
    return isinstance(observed, dict) and observed.get("failure_origin") in {"platform", "cancelled"}


__all__ = ["evaluate_outcome_check", "outcome_is_platform_failure"]
