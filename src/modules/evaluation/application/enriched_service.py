from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from modules.evaluation.application.hardened_service import (
    HardenedEvaluationApplicationService,
)
from modules.evaluation.infra.database.models import (
    EvaluationDatasetVersionModel,
    EvaluationSuiteVersionModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
)


class EnrichedEvaluationApplicationService(HardenedEvaluationApplicationService):
    """Read-model enrichment for authoring provenance and Trial evidence."""

    async def list_suites(self, project_id: UUID) -> list[dict[str, Any]]:
        payload = await super().list_suites(project_id)
        async with self._session_factory() as session:
            for item in payload:
                version_id = item.get("current_version_id")
                if not version_id:
                    continue
                version = await session.get(EvaluationSuiteVersionModel, UUID(str(version_id)))
                if version is None or version.project_id != project_id:
                    continue
                dataset_version = await session.get(
                    EvaluationDatasetVersionModel,
                    version.dataset_version_id,
                )
                case_count = int(
                    await session.scalar(
                        select(func.count(EvaluationTestCaseModel.id)).where(
                            EvaluationTestCaseModel.dataset_version_id
                            == version.dataset_version_id
                        )
                    )
                    or 0
                )
                item.update(
                    {
                        "deterministic_checks": version.deterministic_checks,
                        "case_count": case_count,
                        "authoring_source": (
                            dataset_version.authoring_source
                            if dataset_version is not None
                            else "manual"
                        ),
                        "source_snapshot_hash": (
                            dataset_version.source_snapshot_hash
                            if dataset_version is not None
                            else None
                        ),
                        "source_context_hash": (
                            dataset_version.source_context_hash
                            if dataset_version is not None
                            else None
                        ),
                        "authoring_metadata": (
                            dataset_version.authoring_metadata
                            if dataset_version is not None
                            else None
                        ),
                        "reviewed_at": (
                            dataset_version.reviewed_at
                            if dataset_version is not None
                            else None
                        ),
                    }
                )
        return payload

    async def get_dataset(self, project_id: UUID, dataset_id: UUID) -> dict[str, Any]:
        payload = await super().get_dataset(project_id, dataset_id)
        async with self._session_factory() as session:
            versions = list(
                (
                    await session.scalars(
                        select(EvaluationDatasetVersionModel).where(
                            EvaluationDatasetVersionModel.dataset_id == dataset_id,
                            EvaluationDatasetVersionModel.project_id == project_id,
                        )
                    )
                ).all()
            )
            versions_by_id = {str(item.id): item for item in versions}
            for item in payload.get("versions", []):
                row = versions_by_id.get(str(item.get("id")))
                if row is None:
                    continue
                item.update(
                    {
                        "authoring_source": row.authoring_source,
                        "source_snapshot_hash": row.source_snapshot_hash,
                        "source_context_hash": row.source_context_hash,
                        "authoring_metadata": row.authoring_metadata,
                        "reviewed_at": row.reviewed_at,
                        "reviewed_by": str(row.reviewed_by) if row.reviewed_by else None,
                    }
                )
            current_id = payload.get("current_version_id")
            current = versions_by_id.get(str(current_id)) if current_id else None
            if current is not None:
                payload.update(
                    {
                        "authoring_source": current.authoring_source,
                        "source_snapshot_hash": current.source_snapshot_hash,
                        "source_context_hash": current.source_context_hash,
                        "authoring_metadata": current.authoring_metadata,
                        "reviewed_at": current.reviewed_at,
                    }
                )
        return payload

    async def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, Any]:
        payload = await super().get_run(project_id, run_id)
        async with self._session_factory() as session:
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run_id,
                            EvaluationTrialModel.project_id == project_id,
                        )
                    )
                ).all()
            )
            trial_by_id = {str(item.id): item for item in trials}
            case_ids = [item.test_case_id for item in trials]
            cases = (
                list(
                    (
                        await session.scalars(
                            select(EvaluationTestCaseModel).where(
                                EvaluationTestCaseModel.id.in_(case_ids),
                                EvaluationTestCaseModel.project_id == project_id,
                            )
                        )
                    ).all()
                )
                if case_ids
                else []
            )
            cases_by_id = {item.id: item for item in cases}
            for item in payload.get("trials", []):
                row = trial_by_id.get(str(item.get("id")))
                if row is None:
                    continue
                case = cases_by_id.get(row.test_case_id)
                item.update(
                    {
                        "observed_outcome": row.observed_outcome,
                        "failure_origin": row.failure_origin,
                        "failure_stage": row.failure_stage,
                    }
                )
                if isinstance(item.get("case"), dict) and case is not None:
                    item["case"]["case_type"] = case.case_type

            calls = list(
                (
                    await session.scalars(
                        select(EvaluatorModelCallModel).where(
                            EvaluatorModelCallModel.evaluation_run_id == run_id,
                            EvaluatorModelCallModel.project_id == project_id,
                        )
                    )
                ).all()
            )
            calls_by_id = {str(item.id): item for item in calls}
            for item in payload.get("judge_calls", []):
                row = calls_by_id.get(str(item.get("id")))
                if row is None:
                    continue
                item.update(
                    {
                        "input_tokens": row.input_tokens,
                        "output_tokens": row.output_tokens,
                        "pricing_snapshot": row.pricing_snapshot,
                        "cost_reason": row.cost_reason,
                    }
                )
        return payload


__all__ = ["EnrichedEvaluationApplicationService"]
