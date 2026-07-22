from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.completed_service import (
    CompletedEvaluationApplicationService,
)
from modules.evaluation.infra.database.models import (
    EvaluationCheckResultModel,
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
    ReleaseQualificationModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


_ACTIVE_RUN_STATUSES = {
    "queued",
    "snapshotting",
    "executing",
    "judging",
    "aggregating",
    "cancel_requested",
}
_TERMINAL_TRIAL_STATUSES = {"completed", "failed", "inconclusive", "cancelled"}


class EvaluationExperienceService(CompletedEvaluationApplicationService):
    """MVP facade for simple setup, model variants and lightweight progress."""

    async def _resolve_target_dict(
        self,
        session,
        *,
        project_id: UUID,
        raw: dict[str, Any] | None,
    ):
        resolved = await super()._resolve_target_dict(
            session,
            project_id=project_id,
            raw=raw,
        )
        variant = raw.get("variant") if isinstance(raw, dict) else None
        if not isinstance(variant, dict):
            return resolved
        if str(variant.get("type") or "") != "model_override":
            raise ValidationError("Evaluation target variant type is invalid")
        if resolved.target_type != "agent":
            raise ValidationError("Model comparison variants are supported only for Agents")
        provider_model_id = variant.get("provider_model_id")
        if not provider_model_id:
            raise ValidationError("Model comparison requires provider_model_id")
        try:
            provider_model_uuid = UUID(str(provider_model_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Model comparison provider_model_id is invalid") from exc
        provider_model = await session.get(ProviderModelModel, provider_model_uuid)
        if (
            provider_model is None
            or provider_model.project_id != project_id
            or provider_model.status != "active"
        ):
            raise NotFoundError("Comparison Provider Model is unavailable for this Project")
        credential = await session.get(
            ProviderCredentialModel,
            provider_model.provider_credential_id,
        )
        if (
            credential is None
            or credential.project_id != project_id
            or credential.status != "active"
        ):
            raise NotFoundError("Comparison Provider Credential is unavailable for this Project")

        snapshot = dict(resolved.snapshot or {})
        temperature = variant.get("temperature", snapshot.get("temperature"))
        if temperature is not None:
            temperature = float(temperature)
            if temperature < 0 or temperature > 2:
                raise ValidationError("Model comparison temperature must be between 0 and 2")
        max_output_tokens = variant.get(
            "max_output_tokens",
            snapshot.get("max_output_tokens"),
        )
        if max_output_tokens is not None:
            max_output_tokens = int(max_output_tokens)
            if max_output_tokens < 128 or max_output_tokens > 32768:
                raise ValidationError(
                    "Model comparison max_output_tokens must be between 128 and 32768"
                )
        base_hash = resolved.snapshot_hash
        snapshot.update(
            {
                "provider": credential.provider,
                "model": provider_model.model,
                "provider_model_id": str(provider_model.id),
                "provider_credential_id": str(provider_model.provider_credential_id),
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "base_url": (
                    (provider_model.meta or {}).get("base_url")
                    or (credential.meta or {}).get("base_url")
                    if credential.provider == "custom"
                    else None
                ),
                "evaluation_variant": {
                    "type": "model_override",
                    "base_snapshot_hash": base_hash,
                    "provider_model_id": str(provider_model.id),
                    "provider_model_name": provider_model.name,
                    "model": provider_model.model,
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                },
            }
        )
        return replace(
            resolved,
            snapshot=snapshot,
            snapshot_hash=canonical_hash(snapshot),
            display_version=f"{resolved.display_version} · {provider_model.name}",
        )

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
        elapsed_seconds = None
        if run.started_at is not None:
            end = run.completed_at
            if end is None:
                from datetime import datetime, timezone

                end = datetime.now(timezone.utc)
            elapsed_seconds = max(
                0,
                round((end - run.started_at).total_seconds()),
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
            "total_trials": len(trials),
            "runtime_completed": runtime_completed,
            "runtime_pending": max(0, len(trials) - runtime_completed),
            "judge_completed": judge_completed,
            "judge_running": judging,
            "judge_pending": max(0, runtime_completed - judge_completed - judging),
            "completed_trials": terminal,
            "inconclusive_trials": inconclusive,
            "failed_trials": failed,
            "elapsed_seconds": elapsed_seconds,
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
                raise ConflictError("Wait for the current Evaluation Run to finish before retrying judgments")
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
                raise ConflictError("No completed Agent evidence has a retryable Judge failure")

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
            aggregate = dict(run.aggregate_result or {})
            aggregate["judgment_retry"] = {
                "trial_count": len(eligible),
                "preserved_runtime_evidence": True,
            }
            run.aggregate_result = aggregate
            targets = await self._targets_for_run(session, run.id)
            payload = self._run_payload(run, targets)
            payload["retried_judgment_count"] = len(eligible)
            return payload


__all__ = ["EvaluationExperienceService"]
