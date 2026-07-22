from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.evidence_revision_snapshot import (
    capture_evidence_revision,
)
from modules.evaluation.application.failure_taxonomy import classify_evaluation_failure
from modules.evaluation.application.revision_aware_experience import (
    RevisionAwareEvaluationExperienceService,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTrialModel,
)
from shared.infra.errors import ConflictError, NotFoundError

_ACTIVE = {
    "queued",
    "snapshotting",
    "executing",
    "judging",
    "aggregating",
    "cancel_requested",
}
_TERMINAL_CANCELLED = {"cancelled", "cancel_requested"}


class EvaluationRunRecoveryService(RevisionAwareEvaluationExperienceService):
    """Resume only recoverable incomplete work inside one Evaluation Run."""

    async def resume_run(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        idempotency_key: str,
    ) -> dict[str, Any]:
        normalized_key = idempotency_key.strip()
        judge_trial_ids: list[UUID] = []
        reset_runtime = 0

        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
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
            aggregate = (
                dict(run.aggregate_result)
                if isinstance(run.aggregate_result, dict)
                else {}
            )
            previous_resume = aggregate.get("_resume")
            if (
                isinstance(previous_resume, dict)
                and previous_resume.get("idempotency_key") == normalized_key
            ):
                return self._run_payload(run, targets)
            if run.status in _ACTIVE:
                return self._run_payload(run, targets)
            if run.status in _TERMINAL_CANCELLED:
                raise ConflictError("Cancelled Evaluation Runs cannot be resumed")

            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            if not trials:
                run.status = "queued"
                run.completed_at = None
                run.failure_code = None
                run.failure_detail = None
                aggregate["_resume"] = {
                    "idempotency_key": normalized_key,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "runtime_trials_reset": 0,
                    "judgments_reset": 0,
                }
                run.aggregate_result = aggregate
                return self._run_payload(run, targets)

            await capture_evidence_revision(
                session,
                run,
                reason="before_run_resume",
            )

            for trial in trials:
                output_preserved = isinstance(trial.output_payload, dict)
                if output_preserved and (
                    trial.score is None
                    or trial.passed is None
                    or trial.failure_stage == "judge"
                    or str(trial.failure_code or "").startswith("judge")
                ):
                    judge_trial_ids.append(trial.id)
                    continue
                if trial.status not in {"failed", "blocked", "inconclusive"}:
                    continue
                classification = classify_evaluation_failure(
                    trial_status=trial.status,
                    failure_code=trial.failure_code,
                    failure_detail=trial.failure_detail,
                    runtime_completed=output_preserved,
                )
                if not classification or classification["recoverability"] == "not_retryable":
                    continue
                trial.status = "pending"
                trial.failure_code = None
                trial.failure_detail = None
                trial.failure_origin = None
                trial.failure_stage = None
                trial.started_at = None
                trial.runtime_completed_at = None
                trial.judge_started_at = None
                trial.judge_completed_at = None
                trial.completed_at = None
                reset_runtime += 1

            if reset_runtime == 0 and not judge_trial_ids:
                raise ConflictError(
                    "Evaluation Run has no recoverable pending work. Structural failures require a new Run."
                )

            run.status = "queued"
            run.completed_at = None
            run.failure_code = None
            run.failure_detail = None
            run.overall_score = None
            run.pass_rate = None
            run.qualification_status = None
            run.cancel_requested_at = None
            run.lease_owner = None
            run.lease_expires_at = None
            aggregate["_resume"] = {
                "idempotency_key": normalized_key,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "runtime_trials_reset": reset_runtime,
                "judgments_reset": len(judge_trial_ids),
            }
            run.aggregate_result = aggregate

        if judge_trial_ids:
            return await super().retry_judgments(
                project_id=project_id,
                run_id=run_id,
                trial_ids=judge_trial_ids,
                failure_codes=None,
            )
        return await self.get_run(project_id, run_id)


__all__ = ["EvaluationRunRecoveryService"]
