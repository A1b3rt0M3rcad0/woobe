from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.domain.enums import EvaluationMode
from shared.infra.errors import ConflictError, ValidationError


def target(*, snapshot_hash: str, variant: dict | None = None):
    snapshot = {}
    if variant is not None:
        snapshot["evaluation_variant"] = variant
    return SimpleNamespace(snapshot_hash=snapshot_hash, snapshot=snapshot)


def service() -> EvaluationExperienceService:
    return EvaluationExperienceService.__new__(EvaluationExperienceService)


def test_model_experiment_keeps_reference_target_exact() -> None:
    reference = target(snapshot_hash="base-hash")
    experimental = target(
        snapshot_hash="variant-hash",
        variant={
            "type": "model_override",
            "base_snapshot_hash": "base-hash",
            "qualification_eligible": False,
        },
    )

    assert service()._run_mode(reference, experimental) == EvaluationMode.MODEL_EXPERIMENT.value


def test_reference_target_cannot_override_its_model() -> None:
    reference = target(
        snapshot_hash="variant-a",
        variant={
            "type": "model_override",
            "base_snapshot_hash": "base-hash",
        },
    )
    experimental = target(
        snapshot_hash="variant-b",
        variant={
            "type": "model_override",
            "base_snapshot_hash": "base-hash",
        },
    )

    with pytest.raises(ValidationError, match="reference Agent target"):
        service()._run_mode(reference, experimental)


def test_experimental_target_must_derive_from_reference_hash() -> None:
    reference = target(snapshot_hash="base-hash")
    experimental = target(
        snapshot_hash="variant-hash",
        variant={
            "type": "model_override",
            "base_snapshot_hash": "another-hash",
        },
    )

    with pytest.raises(ConflictError, match="exact same Agent snapshot"):
        service()._run_mode(reference, experimental)


def test_normal_snapshot_comparison_remains_qualification_eligible_mode() -> None:
    candidate = target(snapshot_hash="candidate")
    baseline = target(snapshot_hash="baseline")

    assert service()._run_mode(candidate, baseline) == EvaluationMode.COMPARISON.value
