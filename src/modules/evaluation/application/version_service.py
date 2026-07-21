from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.infra.database.models import (
    EvaluationDatasetVersionModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import NotFoundError, ValidationError


class EvaluationVersionApplicationService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def create_suite_version(
        self,
        *,
        project_id: UUID,
        suite_id: UUID,
        dataset_version_id: UUID,
        judge_provider_model_id: UUID,
        judge_config: dict[str, Any],
        rubric: dict[str, Any],
        deterministic_checks: dict[str, Any],
        acceptance_policy: dict[str, Any],
        repetition_policy: dict[str, Any],
        estimate_defaults: dict[str, Any],
        created_by: UUID,
    ) -> dict[str, Any]:
        self._validate_policy(
            judge_config=judge_config,
            acceptance_policy=acceptance_policy,
            repetition_policy=repetition_policy,
            estimate_defaults=estimate_defaults,
        )
        async with self._session_factory() as session, session.begin():
            suite = await session.get(EvaluationSuiteModel, suite_id, with_for_update=True)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            dataset_version = await session.get(
                EvaluationDatasetVersionModel,
                dataset_version_id,
            )
            if dataset_version is None or dataset_version.project_id != project_id:
                raise NotFoundError("Evaluation Dataset version not found")
            provider_model = await session.get(
                ProviderModelModel,
                judge_provider_model_id,
            )
            if (
                provider_model is None
                or provider_model.project_id != project_id
                or provider_model.status != "active"
            ):
                raise NotFoundError("Evaluator Provider Model not found")
            count = int(
                await session.scalar(
                    select(func.count(EvaluationSuiteVersionModel.id)).where(
                        EvaluationSuiteVersionModel.suite_id == suite.id
                    )
                )
                or 0
            )
            snapshot = {
                "schema_version": 1,
                "dataset_version_id": str(dataset_version_id),
                "judge_provider_model_id": str(judge_provider_model_id),
                "judge_config": judge_config,
                "rubric": rubric,
                "deterministic_checks": deterministic_checks,
                "acceptance_policy": acceptance_policy,
                "repetition_policy": repetition_policy,
                "estimate_defaults": estimate_defaults,
            }
            version = EvaluationSuiteVersionModel(
                suite_id=suite.id,
                project_id=project_id,
                version=f"v{count + 1}",
                dataset_version_id=dataset_version_id,
                judge_provider_model_id=judge_provider_model_id,
                judge_config=judge_config,
                rubric=rubric,
                deterministic_checks=deterministic_checks,
                acceptance_policy=acceptance_policy,
                repetition_policy=repetition_policy,
                estimate_defaults=estimate_defaults,
                suite_hash=canonical_hash(snapshot),
                created_by=created_by,
            )
            session.add(version)
            await session.flush()
            suite.current_version_id = version.id
            await session.flush()
            return {
                "id": str(suite.id),
                "project_id": str(project_id),
                "name": suite.name,
                "description": suite.description,
                "target_type": suite.target_type,
                "status": suite.status,
                "current_version_id": str(version.id),
                "current_version": version.version,
                "dataset_version_id": str(version.dataset_version_id),
                "judge_provider_model_id": str(version.judge_provider_model_id),
                "judge_config": version.judge_config,
                "rubric": version.rubric,
                "deterministic_checks": version.deterministic_checks,
                "acceptance_policy": version.acceptance_policy,
                "repetition_policy": version.repetition_policy,
                "estimate_defaults": version.estimate_defaults,
                "suite_hash": version.suite_hash,
                "created_at": suite.created_at,
                "updated_at": suite.updated_at,
            }

    @staticmethod
    def _validate_policy(
        *,
        judge_config: dict[str, Any],
        acceptance_policy: dict[str, Any],
        repetition_policy: dict[str, Any],
        estimate_defaults: dict[str, Any],
    ) -> None:
        minimum_score = float(acceptance_policy.get("minimum_score", 70))
        minimum_pass_rate = float(acceptance_policy.get("minimum_pass_rate", 80))
        if not 0 <= minimum_score <= 100:
            raise ValidationError("minimum_score must be between 0 and 100")
        if not 0 <= minimum_pass_rate <= 100:
            raise ValidationError("minimum_pass_rate must be between 0 and 100")
        minimum_paired_n = int(acceptance_policy.get("minimum_paired_n", 1))
        if minimum_paired_n < 1:
            raise ValidationError("minimum_paired_n must be at least 1")
        maximum_repetitions = int(repetition_policy.get("maximum_repetitions", 25))
        default_repetitions = int(repetition_policy.get("default_repetitions", 3))
        if not 1 <= maximum_repetitions <= 25:
            raise ValidationError("maximum_repetitions must be between 1 and 25")
        if not 1 <= default_repetitions <= maximum_repetitions:
            raise ValidationError(
                "default_repetitions must be within the configured maximum"
            )
        if int(estimate_defaults.get("volume", 10_000)) < 1:
            raise ValidationError("Estimator volume must be positive")
        timeout_seconds = float(judge_config.get("timeout_seconds", 90))
        if not 5 <= timeout_seconds <= 180:
            raise ValidationError("Judge timeout must be between 5 and 180 seconds")


__all__ = ["EvaluationVersionApplicationService"]
