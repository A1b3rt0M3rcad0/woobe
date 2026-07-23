from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.enriched_service import EnrichedEvaluationApplicationService
from modules.evaluation.application.scoring import build_estimate
from modules.evaluation.application.target_resolver import EvaluationTargetResolver
from modules.evaluation.domain.contracts import validate_suite_draft
from modules.evaluation.infra.database.models import (
    EstimateRunModel,
    EvaluationAuthoringCallModel,
    EvaluationDatasetModel,
    EvaluationDatasetVersionModel,
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _version_number(value: str | None) -> int:
    try:
        return int(str(value or "v0").removeprefix("v"))
    except ValueError:
        return 0


class OperationalEvaluationApplicationService(EnrichedEvaluationApplicationService):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        super().__init__(session_factory)
        self._session_factory = session_factory
        self._target_resolver = EvaluationTargetResolver(session_factory)

    async def list_suites(
        self,
        project_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        payload = await super().list_suites(project_id)
        result = [
            item
            for item in payload
            if include_archived or item.get("status") != "archived"
        ]
        async with self._session_factory() as session:
            for item in result:
                item["staleness"] = await self._suite_staleness(
                    session,
                    project_id=project_id,
                    item=item,
                )
        return result

    async def archive_dataset(
        self,
        project_id: UUID,
        dataset_id: UUID,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationDatasetModel, dataset_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Dataset not found")
            row.status = "archived"
            row.archived_at = _now()
            row.archived_by = user_id
        return await self.get_dataset(project_id, dataset_id)

    async def restore_dataset(
        self,
        project_id: UUID,
        dataset_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationDatasetModel, dataset_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Dataset not found")
            row.status = "active"
            row.archived_at = None
            row.archived_by = None
        return await self.get_dataset(project_id, dataset_id)

    async def archive_suite(
        self,
        project_id: UUID,
        suite_id: UUID,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationSuiteModel, suite_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            row.status = "archived"
            row.archived_at = _now()
            row.archived_by = user_id
        values = await self.list_suites(project_id, include_archived=True)
        return next(item for item in values if item["id"] == str(suite_id))

    async def restore_suite(self, project_id: UUID, suite_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationSuiteModel, suite_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            row.status = "active"
            row.archived_at = None
            row.archived_by = None
        values = await self.list_suites(project_id, include_archived=True)
        return next(item for item in values if item["id"] == str(suite_id))

    async def create_composed_suite_version(
        self,
        *,
        project_id: UUID,
        suite_id: UUID,
        draft: dict[str, Any],
        change_description: str,
        judge_provider_model_id: UUID | None,
        judge_config: dict[str, Any] | None,
        rubric: dict[str, Any] | None,
        deterministic_checks: dict[str, Any] | None,
        acceptance_policy: dict[str, Any] | None,
        repetition_policy: dict[str, Any] | None,
        estimate_defaults: dict[str, Any] | None,
        authoring_source: str,
        source_snapshot_hash: str | None,
        source_context_hash: str | None,
        authoring_metadata: dict[str, Any] | None,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        validation = validate_suite_draft(draft)
        if not validation["valid"]:
            summary = "; ".join(
                f"{item.get('path')}: {item.get('message')}"
                for item in validation["errors"][:10]
            )
            raise ValidationError("Invalid Evaluator Suite draft: " + summary)
        if len(change_description.strip()) < 3:
            raise ValidationError("Suite version change description is required")

        async with self._session_factory() as session, session.begin():
            suite = await session.get(EvaluationSuiteModel, suite_id, with_for_update=True)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            if suite.status == "archived":
                raise ConflictError("Archived Evaluation Suite cannot receive a new version")
            current = await session.get(EvaluationSuiteVersionModel, suite.current_version_id)
            if current is None:
                raise NotFoundError("Current Evaluation Suite version not found")
            current_dataset = await session.get(
                EvaluationDatasetVersionModel,
                current.dataset_version_id,
            )
            if current_dataset is None:
                raise NotFoundError("Current Evaluation Dataset version not found")
            dataset = await session.get(EvaluationDatasetModel, current_dataset.dataset_id, with_for_update=True)
            if dataset is None:
                raise NotFoundError("Evaluation Dataset not found")

            dataset_version_value = f"v{_version_number(current_dataset.version) + 1}"
            suite_version_value = f"v{_version_number(current.version) + 1}"
            cases = validation["cases"]
            dataset_version = EvaluationDatasetVersionModel(
                dataset_id=dataset.id,
                project_id=project_id,
                version=dataset_version_value,
                content_hash=canonical_hash(cases),
                change_description=change_description.strip(),
                authoring_source=authoring_source,
                source_snapshot_hash=source_snapshot_hash,
                source_context_hash=source_context_hash,
                authoring_metadata={
                    **(authoring_metadata or {}),
                    "validation": {
                        "warnings": validation["warnings"],
                        "coverage": validation["coverage"],
                    },
                },
                reviewed_at=_now(),
                reviewed_by=created_by,
                created_by=created_by,
            )
            session.add(dataset_version)
            await session.flush()
            session.add_all(
                [
                    EvaluationTestCaseModel(
                        dataset_version_id=dataset_version.id,
                        project_id=project_id,
                        position=index,
                        name=item["name"],
                        case_type=item["case_type"],
                        input_payload=item["input_payload"],
                        initial_context=item["initial_context"],
                        expected_contract=item["expected_contract"],
                        severity=item["severity"],
                        weight=item["weight"],
                        blocking=item["blocking"],
                        tags=item["tags"],
                        production_frequency=item["production_frequency"],
                    )
                    for index, item in enumerate(cases, start=1)
                ]
            )
            dataset.current_version_id = dataset_version.id

            resolved_judge = judge_provider_model_id or current.judge_provider_model_id
            resolved_judge_config = judge_config or current.judge_config
            resolved_rubric = rubric or current.rubric
            resolved_checks = deterministic_checks or current.deterministic_checks
            resolved_acceptance = acceptance_policy or current.acceptance_policy
            resolved_repetitions = repetition_policy or current.repetition_policy
            resolved_estimates = estimate_defaults or current.estimate_defaults
            suite_version = EvaluationSuiteVersionModel(
                suite_id=suite.id,
                project_id=project_id,
                version=suite_version_value,
                parent_version_id=current.id,
                change_description=change_description.strip(),
                dataset_version_id=dataset_version.id,
                judge_provider_model_id=resolved_judge,
                judge_config=resolved_judge_config,
                rubric=resolved_rubric,
                deterministic_checks=resolved_checks,
                acceptance_policy=resolved_acceptance,
                repetition_policy=resolved_repetitions,
                estimate_defaults=resolved_estimates,
                suite_hash=canonical_hash(
                    {
                        "dataset_version_id": str(dataset_version.id),
                        "judge_provider_model_id": str(resolved_judge),
                        "judge_config": resolved_judge_config,
                        "rubric": resolved_rubric,
                        "deterministic_checks": resolved_checks,
                        "acceptance_policy": resolved_acceptance,
                        "repetition_policy": resolved_repetitions,
                        "estimate_defaults": resolved_estimates,
                    }
                ),
                created_by=created_by,
            )
            session.add(suite_version)
            await session.flush()
            suite.current_version_id = suite_version.id

        values = await self.list_suites(project_id, include_archived=True)
        return next(item for item in values if item["id"] == str(suite_id))

    async def create_estimate(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        volume: int,
        volume_unit: str,
        created_by: UUID | None,
    ) -> list[dict[str, Any]]:
        if volume < 1 or volume > 1_000_000_000:
            raise ValidationError("Estimate volume must be between 1 and 1,000,000,000")
        volume_unit = str(volume_unit).strip().lower()
        if volume_unit not in {"runs_per_month", "sessions_per_month"}:
            raise ValidationError(
                "Estimate volume_unit must be runs_per_month or sessions_per_month"
            )
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run.id,
                            EvaluationTrialModel.status == "completed",
                        )
                    )
                ).all()
            )
            target_by_id = {item.id: item for item in targets}
            created: list[EstimateRunModel] = []
            for target in targets:
                values = []
                for trial in trials:
                    if trial.evaluation_target_id != target.id:
                        continue
                    metrics = trial.metrics or {}
                    checks = metrics.get("checks") if isinstance(metrics.get("checks"), dict) else {}
                    values.append(
                        {
                            "id": str(trial.id),
                            "pair_key": trial.pair_key,
                            "side": target.side,
                            "status": trial.status,
                            "score": trial.score,
                            "passed": trial.passed,
                            "metrics": metrics,
                            "critical_failures": int(checks.get("critical_failures") or 0),
                            "warning_count": int(checks.get("warning_count") or 0),
                        }
                    )
                if volume_unit == "sessions_per_month":
                    values = [
                        item
                        for item in values
                        if (item.get("metrics") or {}).get("interaction_mode")
                        == "session"
                    ]
                    if not values:
                        raise ValidationError(
                            "sessions_per_month requires completed Session Trial evidence"
                        )
                estimate = build_estimate(
                    values=values,
                    volume=volume,
                    target_type=target.target_type,
                    volume_unit=volume_unit,
                )
                existing = await session.scalar(
                    select(EstimateRunModel).where(
                        EstimateRunModel.evaluation_run_id == run.id,
                        EstimateRunModel.target_id == target.id,
                        EstimateRunModel.volume == volume,
                        EstimateRunModel.volume_unit == volume_unit,
                        EstimateRunModel.price_snapshot_hash == "none",
                    )
                )
                if existing is not None:
                    created.append(existing)
                    continue
                row = EstimateRunModel(
                    project_id=project_id,
                    evaluation_run_id=run.id,
                    target_id=target.id,
                    volume_unit=volume_unit,
                    volume=volume,
                    assumptions={
                        "projection_method": "observed_trial_distribution",
                        "run_purpose": "evaluation",
                        "volume_unit": volume_unit,
                    },
                    observation_summary=estimate["observation_summary"],
                    price_snapshot=None,
                    price_snapshot_hash="none",
                    scenarios=estimate["scenarios"],
                    confidence=estimate["confidence"],
                    limitations=estimate["limitations"],
                    created_by=created_by,
                )
                session.add(row)
                created.append(row)
            await session.flush()
            return [
                {
                    "id": str(item.id),
                    "target_id": str(item.target_id),
                    "target_type": target_by_id[item.target_id].target_type,
                    "volume": item.volume,
                    "volume_unit": item.volume_unit,
                    "confidence": item.confidence,
                    "observation_summary": item.observation_summary,
                    "scenarios": item.scenarios,
                    "limitations": item.limitations,
                    "created_at": item.created_at,
                }
                for item in created
            ]

    async def _suite_staleness(
        self,
        session,
        *,
        project_id: UUID,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        source_hash = item.get("source_snapshot_hash")
        if not source_hash:
            return {"status": "generic", "source_snapshot_hash": None, "current_snapshot_hash": None}
        metadata = item.get("authoring_metadata") if isinstance(item.get("authoring_metadata"), dict) else {}
        call_id = metadata.get("authoring_call_id")
        call = None
        if call_id:
            try:
                call = await session.get(EvaluationAuthoringCallModel, UUID(str(call_id)))
            except (TypeError, ValueError):
                call = None
        if call is None or call.project_id != project_id:
            return {
                "status": "current_unknown",
                "source_snapshot_hash": source_hash,
                "current_snapshot_hash": None,
            }
        try:
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=call.target_type,
                source_type=call.target_source_type,
                entity_id=call.target_entity_id,
                version_id=None,
            )
        except Exception:
            return {
                "status": "target_unavailable",
                "source_snapshot_hash": source_hash,
                "current_snapshot_hash": None,
            }
        return {
            "status": "current" if resolved.snapshot_hash == source_hash else "stale",
            "source_snapshot_hash": source_hash,
            "current_snapshot_hash": resolved.snapshot_hash,
            "target_type": call.target_type,
            "entity_id": str(call.target_entity_id),
            "source_type": call.target_source_type,
            "display_version": resolved.display_version,
        }


__all__ = ["OperationalEvaluationApplicationService"]
