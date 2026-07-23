from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.evaluation.infra.judge import canonical_hash

SCORING_ALGORITHM_VERSION = "evaluation-scoring-v2"
OUTCOME_CLASSIFICATION_VERSION = "evaluation-outcomes-v2"
JUDGE_SCHEMA_VERSION = "evaluation-judge-v3-governed"


def evaluation_protocol_payload(suite: Any, *, repetitions: int | None = None) -> dict[str, Any]:
    """Return the material protocol used to judge compatibility between Runs."""

    payload: dict[str, Any] = {
        "suite_version_id": str(suite.id),
        "dataset_version_id": str(suite.dataset_version_id),
        "judge_provider_model_id": str(suite.judge_provider_model_id),
        "judge_config": suite.judge_config or {},
        "rubric": suite.rubric or {},
        "deterministic_checks": suite.deterministic_checks or {},
        "acceptance_policy": suite.acceptance_policy or {},
        "suite_hash": suite.suite_hash,
        "judge_schema_version": JUDGE_SCHEMA_VERSION,
        "scoring_algorithm_version": SCORING_ALGORITHM_VERSION,
        "outcome_classification_version": OUTCOME_CLASSIFICATION_VERSION,
    }
    if repetitions is not None:
        payload["repetitions"] = int(repetitions)
    return payload


def evaluation_protocol_hash(suite: Any, *, repetitions: int | None = None) -> str:
    return canonical_hash(evaluation_protocol_payload(suite, repetitions=repetitions))


def target_identity_hash(
    *,
    target_type: str,
    entity_id: UUID | str,
    source_type: str,
    target_version_id: UUID | str | None,
    snapshot_hash: str,
) -> str:
    return canonical_hash(
        {
            "target_type": target_type,
            "entity_id": str(entity_id),
            "source_type": source_type,
            "target_version_id": str(target_version_id) if target_version_id else None,
            "snapshot_hash": snapshot_hash,
        }
    )


def protocol_compatibility(
    candidate_hash: str | None,
    reference_hash: str | None,
    *,
    candidate_repetitions: int,
    reference_repetitions: int,
) -> dict[str, Any]:
    if not candidate_hash or not reference_hash:
        return {
            "compatible": False,
            "comparison_kind": "unavailable",
            "reason": "evaluation_protocol_missing",
            "warnings": ["One or both Runs predate protocol hashing."],
        }
    if candidate_hash != reference_hash:
        return {
            "compatible": False,
            "comparison_kind": "descriptive_only",
            "reason": "evaluation_protocol_mismatch",
            "warnings": [
                "The Runs used different Suite, Dataset, Judge, rubric, checks or scoring contracts."
            ],
        }
    warnings: list[str] = []
    kind = "paired"
    if candidate_repetitions != reference_repetitions:
        kind = "historical_aggregate"
        warnings.append("The Runs used different repetition counts.")
    return {
        "compatible": True,
        "comparison_kind": kind,
        "reason": None,
        "warnings": warnings,
    }


__all__ = [
    "JUDGE_SCHEMA_VERSION",
    "OUTCOME_CLASSIFICATION_VERSION",
    "SCORING_ALGORITHM_VERSION",
    "evaluation_protocol_hash",
    "evaluation_protocol_payload",
    "protocol_compatibility",
    "target_identity_hash",
]
