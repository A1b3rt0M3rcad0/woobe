from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.domain.enums import EvaluationMode
from shared.infra.errors import ValidationError


def service() -> EvaluationExperienceService:
    return EvaluationExperienceService.__new__(EvaluationExperienceService)


def target(snapshot_hash: str):
    return SimpleNamespace(snapshot_hash=snapshot_hash, snapshot={})


def test_single_real_snapshot_uses_absolute_mode() -> None:
    assert service()._run_mode(target("production-hash"), None) == EvaluationMode.ABSOLUTE.value


def test_two_real_snapshots_use_comparison_mode() -> None:
    assert service()._run_mode(
        target("candidate-hash"),
        target("baseline-hash"),
    ) == EvaluationMode.COMPARISON.value


@pytest.mark.asyncio
async def test_model_override_is_rejected_before_target_resolution() -> None:
    with pytest.raises(ValidationError, match="Model overrides are not supported"):
        await service()._resolve_target_dict(
            None,
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            raw={
                "target_type": "agent",
                "source_type": "release",
                "entity_id": "00000000-0000-0000-0000-000000000002",
                "version_id": "00000000-0000-0000-0000-000000000003",
                "variant": {
                    "type": "model_override",
                    "provider_model_id": "00000000-0000-0000-0000-000000000004",
                },
            },
        )


def test_model_experiment_mode_is_not_selected_for_new_runs() -> None:
    assert service()._run_mode(
        target("candidate-hash"),
        target("baseline-hash"),
    ) != EvaluationMode.MODEL_EXPERIMENT.value
