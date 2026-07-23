from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.evidence_revision_snapshot import (
    capture_evidence_revision,
)
from modules.evaluation.application.governed_experience_service import (
    GovernedEvaluationExperienceService,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
)
from shared.infra.errors import NotFoundError


def _evidence_revision(run: EvaluationRunModel) -> int:
    aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
    try:
        return max(1, int(aggregate.get("evidence_revision") or 1))
    except (TypeError, ValueError):
        return 1


def _call_snapshot(call: EvaluatorModelCallModel) -> dict:
    diagnostics = None
    if isinstance(call.pricing_snapshot, dict):
        value = call.pricing_snapshot.get("_evaluation_judge")
        diagnostics = value if isinstance(value, dict) else None
    return {
        "model_call_id": str(call.id),
        "provider_model_id": str(call.provider_model_id),
        "provider": call.provider,
        "model": call.model,
        "status": call.status,
        "judge_config_hash": call.judge_config_hash,
        "rubric_hash": call.rubric_hash,
        "input_tokens": call.input_tokens,
        "output_tokens": call.output_tokens,
        "cost_usd": float(call.cost_usd) if call.cost_usd is not None else None,
        "cost_status": call.cost_status,
        "cost_reason": call.cost_reason,
        "latency_ms": call.latency_ms,
        "error": call.error,
        "structured_result": call.structured_result,
        "diagnostics": diagnostics,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "completed_at": call.completed_at.isoformat() if call.completed_at else None,
        "created_at": call.created_at.isoformat() if call.created_at else None,
    }


class RevisionAwareEvaluationExperienceService(GovernedEvaluationExperienceService):
    """Preserve the current evidence revision and Judge logs before destructive retry."""

    async def retry_judgments(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        trial_ids: list[UUID] | None = None,
        failure_codes: list[str] | None = None,
    ):
        await self._assert_retry_allowed(
            project_id=project_id,
            run_id=run_id,
            trial_ids=trial_ids,
        )
        selected_ids = set(trial_ids or [])
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            revision = _evidence_revision(run)
            await capture_evidence_revision(
                session,
                run,
                reason="before_judgment_retry",
            )
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            calls = list(
                (
                    await session.scalars(
                        select(EvaluatorModelCallModel).where(
                            EvaluatorModelCallModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            calls_by_trial = {item.evaluation_trial_id: item for item in calls}
            for trial in trials:
                if selected_ids and trial.id not in selected_ids:
                    continue
                call = calls_by_trial.get(trial.id)
                if call is None:
                    continue
                metrics = dict(trial.metrics or {})
                history = list(metrics.get("judge_call_history") or [])
                if any(
                    isinstance(item, dict)
                    and item.get("model_call_id") == str(call.id)
                    for item in history
                ):
                    continue
                history.append(
                    {
                        "evidence_revision": revision,
                        "preserved_reason": "before_judgment_retry",
                        **_call_snapshot(call),
                    }
                )
                metrics["judge_call_history"] = history[-10:]
                trial.metrics = metrics
        return await super().retry_judgments(
            project_id=project_id,
            run_id=run_id,
            trial_ids=trial_ids,
            failure_codes=failure_codes,
        )


__all__ = ["RevisionAwareEvaluationExperienceService"]
