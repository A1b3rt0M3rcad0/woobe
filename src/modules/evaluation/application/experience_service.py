from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from modules.evaluation.application.human_decision_service import (
    HumanDecisionEvaluationApplicationService,
    _target_manifest,
)
from modules.evaluation.infra.database.decision_models import (
    EvaluationTargetDecisionModel,
)
from modules.evaluation.infra.database.models import (
    EstimateRunModel,
    EvaluationCheckResultModel,
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
    ReleaseQualificationModel,
)
from shared.infra.errors import ConflictError, NotFoundError

_ACTIVE_RUN_STATUSES = {
    "queued",
    "snapshotting",
    "executing",
    "judging",
    "aggregating",
    "cancel_requested",
}
_TERMINAL_TRIAL_STATUSES = {"completed", "failed", "inconclusive", "cancelled"}


def _safe_preview_target(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    target = SimpleNamespace(**value)
    return {
        "target_type": value.get("target_type"),
        "source_type": value.get("source_type"),
        "entity_id": str(value.get("entity_id")) if value.get("entity_id") else None,
        "environment": value.get("environment"),
        "agent_release_id": str(value.get("agent_release_id"))
        if value.get("agent_release_id")
        else None,
        "network_version_id": str(value.get("network_version_id"))
        if value.get("network_version_id")
        else None,
        "snapshot_hash": value.get("snapshot_hash"),
        "composition_hash": value.get("composition_hash"),
        "display_name": value.get("display_name"),
        "display_version": value.get("display_version"),
        "manifest": _target_manifest(target),
    }


def _revision(aggregate: dict[str, Any]) -> int:
    try:
        return max(1, int(aggregate.get("evidence_revision") or 1))
    except (TypeError, ValueError):
        return 1


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class EvaluationExperienceService(HumanDecisionEvaluationApplicationService):
    """MVP facade for exact snapshot Evaluations and lightweight progress."""

    async def preview_run(self, **kwargs) -> dict[str, Any]:
        payload = await super().preview_run(**kwargs)
        return {
            **payload,
            "candidate": _safe_preview_target(payload.get("candidate")),
            "baseline": _safe_preview_target(payload.get("baseline")),
        }

    async def get_run_progress(
        self,
        project_id: UUID,
        run_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )

        runtime_completed = sum(
            1 for trial in trials if bool((trial.metrics or {}).get("runtime_completed"))
        )
        judging = sum(1 for trial in trials if trial.status == "judging")
        terminal = sum(1 for trial in trials if trial.status in _TERMINAL_TRIAL_STATUSES)
        inconclusive = sum(1 for trial in trials if trial.status == "inconclusive")
        failed = sum(1 for trial in trials if trial.status == "failed")
        judge_completed = sum(1 for trial in trials if trial.judge_completed_at is not None)
        cost = sum(
            float((trial.metrics or {}).get("cost_usd") or 0)
            + float((trial.metrics or {}).get("judge_cost_usd") or 0)
            for trial in trials
        )
        now = datetime.now(timezone.utc)
        aggregate = dict(run.aggregate_result or {})
        retry = aggregate.get("judgment_retry")
        retry = retry if isinstance(retry, dict) else None

        processing_elapsed_seconds = None
        if run.started_at is not None:
            end = run.completed_at or now
            processing_elapsed_seconds = max(
                0,
                round((end - run.started_at).total_seconds()),
            )
        phase_started_at = (
            _parse_datetime(retry.get("started_at"))
            if retry and retry.get("status") in {"queued", "running"}
            else run.started_at
        )
        phase_elapsed_seconds = None
        if phase_started_at is not None:
            phase_end = run.completed_at if run.status not in _ACTIVE_RUN_STATUSES else now
            phase_end = phase_end or now
            phase_elapsed_seconds = max(
                0,
                round((phase_end - phase_started_at).total_seconds()),
            )

        phase = {
            "queued": "preparing",
            "snapshotting": "preparing",
            "executing": "executing_cases",
            "judging": "judging_responses",
            "aggregating": "aggregating_results",
            "completed": "completed",
            "partially_completed": "completed_with_attention",
            "failed": "failed",
            "cancel_requested": "cancelling",
            "cancelled": "cancelled",
        }.get(run.status, run.status)
        return {
            "run_id": str(run.id),
            "status": run.status,
            "phase": phase,
            "mode": run.mode,
            "qualification_eligible": False,
            "decision_required": run.status in {
                "completed",
                "partially_completed",
            },
            "evidence_revision": _revision(aggregate),
            "retry_attempt": int((retry or {}).get("attempt") or 0),
            "retry_trial_count": int((retry or {}).get("trial_count") or 0),
            "total_trials": len(trials),
            "runtime_completed": runtime_completed,
            "runtime_pending": max(0, len(trials) - runtime_completed),
            "judge_completed": judge_completed,
            "judge_running": judging,
            "judge_pending": max(0, runtime_completed - judge_completed - judging),
            "completed_trials": terminal,
            "inconclusive_trials": inconclusive,
            "failed_trials": failed,
            "elapsed_seconds": phase_elapsed_seconds,
            "phase_elapsed_seconds": phase_elapsed_seconds,
            "processing_elapsed_seconds": processing_elapsed_seconds,
            "started_at": run.started_at,
            "measured_cost_usd": cost or run.measured_total_cost,
            "targets": [self._target_payload(target) for target in targets],
            "failure_code": run.failure_code,
            "failure_detail": run.failure_detail,
        }

    async def retry_judgments(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        trial_ids: list[UUID] | None = None,
        failure_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        selected_ids = set(trial_ids or [])
        selected_codes = set(
            failure_codes
            or ["judge_failed", "judge_output_length_limit", "judge_invalid_json"]
        )
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            if run.status in _ACTIVE_RUN_STATUSES:
                raise ConflictError(
                    "Wait for the current Evaluation Run to finish before retrying judgments"
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
            calls_by_trial = {call.evaluation_trial_id: call for call in calls}
            eligible: list[EvaluationTrialModel] = []
            for trial in trials:
                if selected_ids and trial.id not in selected_ids:
                    continue
                if trial.output_payload is None or not bool(
                    (trial.metrics or {}).get("runtime_completed")
                ):
                    continue
                call = calls_by_trial.get(trial.id)
                call_error = str(call.error or "").lower() if call else ""
                code = str(trial.failure_code or "")
                judge_failure = (
                    code in selected_codes
                    or any(value in call_error for value in selected_codes)
                    or (call is not None and call.status == "failed" and not failure_codes)
                )
                if judge_failure:
                    eligible.append(trial)
            if not eligible:
                raise ConflictError(
                    "No completed Agent evidence has a retryable Judge failure"
                )

            now = datetime.now(timezone.utc)
            aggregate = dict(run.aggregate_result or {})
            previous_revision = _revision(aggregate)
            evidence_revision = previous_revision + 1
            previous_retry = aggregate.get("judgment_retry")
            previous_attempt = (
                int(previous_retry.get("attempt") or 0)
                if isinstance(previous_retry, dict)
                else 0
            )

            current_decisions = list(
                (
                    await session.scalars(
                        select(EvaluationTargetDecisionModel).where(
                            EvaluationTargetDecisionModel.evaluation_run_id == run.id,
                            EvaluationTargetDecisionModel.superseded_at.is_(None),
                        )
                    )
                ).all()
            )
            for decision in current_decisions:
                decision.superseded_at = now
                decision.superseded_reason = "judgment_retry"

            estimates = list(
                (
                    await session.scalars(
                        select(EstimateRunModel).where(
                            EstimateRunModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            for estimate in estimates:
                assumptions = dict(estimate.assumptions or {})
                if "evidence_revision" not in assumptions:
                    assumptions["evidence_revision"] = previous_revision
                if int(assumptions.get("evidence_revision") or 1) < evidence_revision:
                    assumptions["superseded_at"] = now.isoformat()
                    assumptions["superseded_reason"] = "judgment_retry"
                estimate.assumptions = assumptions

            eligible_ids = [trial.id for trial in eligible]
            await session.execute(
                delete(EvaluationCheckResultModel).where(
                    EvaluationCheckResultModel.evaluation_trial_id.in_(eligible_ids)
                )
            )
            await session.execute(
                delete(EvaluatorModelCallModel).where(
                    EvaluatorModelCallModel.evaluation_trial_id.in_(eligible_ids)
                )
            )
            await session.execute(
                delete(ReleaseQualificationModel).where(
                    ReleaseQualificationModel.evaluation_run_id == run.id
                )
            )
            for trial in eligible:
                metrics = dict(trial.metrics or {})
                prior_cost = float(metrics.get("judge_cost_usd") or 0)
                accumulated_prior = float(
                    metrics.get("judge_retry_previous_cost_usd") or 0
                )
                metrics["judge_retry_previous_cost_usd"] = (
                    accumulated_prior + prior_cost
                )
                metrics.pop("judge_cost_usd", None)
                metrics.pop("judge_latency_ms", None)
                metrics.pop("checks", None)
                trial.metrics = metrics
                trial.status = "pending"
                trial.score = None
                trial.passed = None
                trial.failure_code = None
                trial.failure_detail = None
                trial.judge_started_at = None
                trial.judge_completed_at = None
                trial.completed_at = None
            run.status = "queued"
            run.qualification_status = None
            run.overall_score = None
            run.pass_rate = None
            run.failure_code = None
            run.failure_detail = None
            run.completed_at = None
            run.lease_owner = None
            run.lease_expires_at = None
            aggregate["evidence_revision"] = evidence_revision
            aggregate["assessment"] = {
                "status": "pending",
                "decision_required": False,
            }
            aggregate["decision"] = {
                "status": "pending",
                "evidence_revision": evidence_revision,
            }
            aggregate["judgment_retry"] = {
                "attempt": previous_attempt + 1,
                "status": "queued",
                "started_at": now.isoformat(),
                "trial_count": len(eligible),
                "preserved_runtime_evidence": True,
                "previous_evidence_revision": previous_revision,
                "evidence_revision": evidence_revision,
            }
            run.aggregate_result = aggregate
            targets = await self._targets_for_run(session, run.id)
            payload = self._run_payload(run, targets)
            payload["retried_judgment_count"] = len(eligible)
            return payload


__all__ = ["EvaluationExperienceService"]
