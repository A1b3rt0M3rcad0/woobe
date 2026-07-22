from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from modules.evaluation.application.evaluation_protocol import (
    evaluation_protocol_hash,
    protocol_compatibility,
    target_identity_hash,
)
from modules.evaluation.application.failure_taxonomy import (
    classify_evaluation_failure,
)
from modules.evaluation.infra.database.catalog_models import (
    EvaluationComparisonDecisionModel,
    EvaluationComparisonModel,
    EvaluationModel,
)
from modules.evaluation.infra.workers.integrity_worker import (
    IntegrityEvaluationRunProcessor,
    IntegrityEvaluationRunWorker,
)


def _suite(**overrides):
    values = {
        "id": uuid4(),
        "dataset_version_id": uuid4(),
        "judge_provider_model_id": uuid4(),
        "judge_config": {"temperature": 0},
        "rubric": {"quality": 1},
        "deterministic_checks": {"enabled": True},
        "acceptance_policy": {"minimum_score": 70},
        "suite_hash": "suite-hash",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_protocol_hash_is_target_independent_and_materially_stable() -> None:
    suite = _suite()
    first = evaluation_protocol_hash(suite)
    second = evaluation_protocol_hash(suite)

    assert first == second
    assert evaluation_protocol_hash(
        _suite(
            id=suite.id,
            dataset_version_id=suite.dataset_version_id,
            judge_provider_model_id=suite.judge_provider_model_id,
            judge_config=suite.judge_config,
            rubric={"quality": 2},
            deterministic_checks=suite.deterministic_checks,
            acceptance_policy=suite.acceptance_policy,
            suite_hash=suite.suite_hash,
        )
    ) != first


def test_target_identity_distinguishes_operational_references() -> None:
    entity_id = uuid4()
    snapshot_hash = "a" * 64

    draft = target_identity_hash(
        target_type="agent",
        entity_id=entity_id,
        source_type="draft",
        target_version_id=None,
        snapshot_hash=snapshot_hash,
    )
    release = target_identity_hash(
        target_type="agent",
        entity_id=entity_id,
        source_type="release",
        target_version_id=uuid4(),
        snapshot_hash=snapshot_hash,
    )

    assert draft != release


def test_comparison_protocol_requires_identical_material_contract() -> None:
    compatible = protocol_compatibility(
        "protocol",
        "protocol",
        candidate_repetitions=3,
        reference_repetitions=3,
    )
    aggregate = protocol_compatibility(
        "protocol",
        "protocol",
        candidate_repetitions=3,
        reference_repetitions=1,
    )
    incompatible = protocol_compatibility(
        "candidate",
        "reference",
        candidate_repetitions=3,
        reference_repetitions=3,
    )

    assert compatible == {
        "compatible": True,
        "comparison_kind": "paired",
        "reason": None,
        "warnings": [],
    }
    assert aggregate["compatible"] is True
    assert aggregate["comparison_kind"] == "historical_aggregate"
    assert incompatible["compatible"] is False
    assert incompatible["reason"] == "evaluation_protocol_mismatch"


def test_judge_failure_taxonomy_preserves_target_output() -> None:
    value = classify_evaluation_failure(
        trial_status="inconclusive",
        failure_code="judge_failed",
        failure_detail="Evaluator Model returned invalid JSON",
        judge_status="failed",
        judge_error="invalid json structured response",
        runtime_completed=True,
    )

    assert value is not None
    assert value["stage"] == "judge"
    assert value["code"] == "judge_invalid_json"
    assert value["recoverability"] == "retryable"


def test_catalog_models_and_integrity_worker_are_importable() -> None:
    assert EvaluationModel is not None
    assert EvaluationComparisonModel is not None
    assert EvaluationComparisonDecisionModel is not None
    assert IntegrityEvaluationRunProcessor is not None
    assert IntegrityEvaluationRunWorker is not None
