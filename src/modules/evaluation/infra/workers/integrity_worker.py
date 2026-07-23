from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.evidence_revision_snapshot import (
    capture_evidence_revision,
)
from modules.evaluation.application.failure_taxonomy import (
    canonical_judge_failure_code,
    judge_failure_policy,
)
from modules.evaluation.application.runtime_gateway import EvaluationRuntimeCancelled
from modules.evaluation.domain.enums import EvaluationTrialStatus
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.governed_judge import GovernedEvaluatorModelGateway
from modules.evaluation.infra.workers.governed_worker import (
    GovernedEvaluationRunProcessor,
    GovernedEvaluationRunWorker,
)
from shared.infra.config import Settings

_CIRCUIT_PREFIX = "judge_circuit_open:"


class IntegrityEvaluationRunProcessor(GovernedEvaluationRunProcessor):
    """Keep unavailable metrics distinct from zero and govern Judge fan-out."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(session_factory, settings=settings)
        self._judge = GovernedEvaluatorModelGateway(settings)
        self._judge_canary_locks: dict[UUID, asyncio.Lock] = {}
        self._judge_canary_holders: dict[UUID, UUID] = {}

    async def _run_judge_state(self, trial_id: UUID) -> tuple[UUID | None, dict[str, Any]]:
        async with self._session_factory() as session:
            trial = await session.get(EvaluationTrialModel, trial_id)
            if trial is None:
                return None, {}
            run = await session.get(EvaluationRunModel, trial.evaluation_run_id)
            aggregate = (
                dict(run.aggregate_result)
                if run is not None and isinstance(run.aggregate_result, dict)
                else {}
            )
            return trial.evaluation_run_id, aggregate

    async def _mark_judge_started(self, trial_id: UUID) -> None:
        run_id, aggregate = await self._run_judge_state(trial_id)
        if run_id is None:
            return await super()._mark_judge_started(trial_id)
        circuit = aggregate.get("judge_circuit_breaker")
        if isinstance(circuit, dict) and circuit.get("status") == "open":
            code = str(circuit.get("code") or "judge_terminal_failure")
            detail = str(circuit.get("detail") or "Judge circuit breaker is open")
            raise EvaluationRuntimeCancelled(f"{_CIRCUIT_PREFIX}{code}:{detail}")

        canary = aggregate.get("judge_canary")
        canary_complete = isinstance(canary, dict) and canary.get("status") in {
            "passed",
            "failed_non_terminal",
        }
        acquired_canary = False
        if not canary_complete:
            lock = self._judge_canary_locks.setdefault(run_id, asyncio.Lock())
            await lock.acquire()
            acquired_canary = True
            self._judge_canary_holders[trial_id] = run_id
            _, refreshed = await self._run_judge_state(trial_id)
            circuit = refreshed.get("judge_circuit_breaker")
            if isinstance(circuit, dict) and circuit.get("status") == "open":
                self._release_canary(trial_id)
                code = str(circuit.get("code") or "judge_terminal_failure")
                detail = str(circuit.get("detail") or "Judge circuit breaker is open")
                raise EvaluationRuntimeCancelled(f"{_CIRCUIT_PREFIX}{code}:{detail}")
            refreshed_canary = refreshed.get("judge_canary")
            if isinstance(refreshed_canary, dict) and refreshed_canary.get("status") in {
                "passed",
                "failed_non_terminal",
            }:
                self._release_canary(trial_id)
                acquired_canary = False
        try:
            await super()._mark_judge_started(trial_id)
        except Exception:
            if acquired_canary:
                self._release_canary(trial_id)
            raise

    async def _persist_final_result(self, **kwargs: Any) -> None:
        trial = kwargs["trial"]
        judge = kwargs["judge"]
        try:
            await super()._persist_final_result(**kwargs)
            async with self._session_factory() as session, session.begin():
                row = await session.get(
                    EvaluationTrialModel,
                    trial.id,
                    with_for_update=True,
                )
                run = await session.get(
                    EvaluationRunModel,
                    trial.evaluation_run_id,
                    with_for_update=True,
                )
                if row is None:
                    return
                metrics = dict(row.metrics or {})
                diagnostics = None
                pricing_snapshot = judge.pricing_snapshot or {}
                if isinstance(pricing_snapshot, dict):
                    value = pricing_snapshot.get("_evaluation_judge")
                    diagnostics = value if isinstance(value, dict) else None
                if diagnostics is not None:
                    metrics["judge_diagnostics"] = diagnostics
                metrics["judge_latency_ms"] = judge.latency_ms
                metrics["evaluation_worker"] = {
                    "processor": "IntegrityEvaluationRunProcessor",
                    "processor_version": "integrity-evaluation-worker-v2",
                    "judge_gateway": "GovernedEvaluatorModelGateway",
                    "expected_adaptive_gateway": "adaptive-judge-v4",
                    "expected_governed_gateway": "governed-judge-v1",
                }
                row.metrics = metrics
                canonical = None
                if judge.structured_result is None:
                    canonical = canonical_judge_failure_code(
                        failure_code=row.failure_code,
                        failure_detail=row.failure_detail,
                        judge_status=judge.status,
                        judge_error=judge.error,
                    )
                    if canonical is not None:
                        row.failure_code = canonical
                if run is not None:
                    aggregate = (
                        dict(run.aggregate_result)
                        if isinstance(run.aggregate_result, dict)
                        else {}
                    )
                    if judge.structured_result is not None:
                        aggregate["judge_canary"] = {
                            "status": "passed",
                            "trial_id": str(trial.id),
                            "provider": judge.provider,
                            "model": judge.model,
                        }
                    elif canonical is not None:
                        policy = judge_failure_policy(canonical)
                        aggregate["judge_canary"] = {
                            "status": (
                                "failed_terminal"
                                if policy.get("circuit_breaker")
                                else "failed_non_terminal"
                            ),
                            "trial_id": str(trial.id),
                            "code": canonical,
                        }
                        if policy.get("circuit_breaker"):
                            aggregate["judge_circuit_breaker"] = {
                                "status": "open",
                                "code": canonical,
                                "detail": str(judge.error or canonical)[:2000],
                                "trigger_trial_id": str(trial.id),
                                "provider_model_id": str(judge.provider_model_id),
                                "provider_credential_id": str(judge.provider_credential_id),
                                "provider": judge.provider,
                                "model": judge.model,
                                "recommended_action": policy.get("recommended_action"),
                            }
                            run.failure_code = canonical
                            run.failure_detail = str(judge.error or canonical)[:4000]
                    run.aggregate_result = aggregate
        finally:
            self._release_canary(trial.id)

    async def _mark_trial_cancelled(self, trial_id: UUID, detail: str) -> None:
        if detail.startswith(_CIRCUIT_PREFIX):
            payload = detail.removeprefix(_CIRCUIT_PREFIX)
            code, _, reason = payload.partition(":")
            async with self._session_factory() as session, session.begin():
                row = await session.get(
                    EvaluationTrialModel,
                    trial_id,
                    with_for_update=True,
                )
                if row is not None:
                    metrics = dict(row.metrics or {})
                    metrics["runtime_completed"] = row.output_payload is not None
                    metrics["judge_skipped"] = {
                        "reason": "run_circuit_breaker",
                        "code": code or "judge_terminal_failure",
                    }
                    row.metrics = metrics
                    row.status = EvaluationTrialStatus.INCONCLUSIVE.value
                    row.failure_code = code or "judge_terminal_failure"
                    row.failure_detail = reason or "Judge circuit breaker opened before this Trial"
                    row.score = None
                    row.passed = None
                    row.judge_completed_at = self._utc_now()
                    row.completed_at = self._utc_now()
            self._release_judge_slot(trial_id)
            self._release_canary(trial_id)
            return
        await super()._mark_trial_cancelled(trial_id, detail)

    @staticmethod
    def _utc_now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)

    def _release_canary(self, trial_id: UUID) -> None:
        run_id = self._judge_canary_holders.pop(trial_id, None)
        if run_id is None:
            return
        lock = self._judge_canary_locks.get(run_id)
        if lock is not None and lock.locked():
            lock.release()

    async def _aggregate(self, run_id: UUID) -> None:
        await super()._aggregate(run_id)
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            conclusive = [
                trial
                for trial in trials
                if trial.score is not None and trial.passed is not None
            ]
            aggregate = (
                dict(run.aggregate_result)
                if isinstance(run.aggregate_result, dict)
                else {}
            )
            assessment = (
                dict(aggregate.get("assessment"))
                if isinstance(aggregate.get("assessment"), dict)
                else {}
            )
            if not conclusive:
                run.overall_score = None
                run.pass_rate = None
                assessment.update(
                    {
                        "status": "inconclusive",
                        "overall_score": None,
                        "pass_rate": None,
                        "qualification_status": "inconclusive",
                        "policy_status": "inconclusive",
                        "decision_required": False,
                        "reason": "no_scored_judge_evidence",
                    }
                )
                for summary in aggregate.get("target_summaries") or []:
                    if isinstance(summary, dict):
                        summary["weighted_score"] = None
                        summary["weighted_pass_rate"] = None
                aggregate["evidence_status"] = "unavailable"
            else:
                aggregate["evidence_status"] = (
                    "complete" if len(conclusive) == len(trials) else "partial"
                )
            aggregate["evidence_completeness"] = {
                "total_trials": len(trials),
                "conclusive_trials": len(conclusive),
                "inconclusive_trials": max(0, len(trials) - len(conclusive)),
            }
            aggregate["assessment"] = assessment
            retry = aggregate.get("judgment_retry")
            if isinstance(retry, dict):
                retry["status"] = "completed"
                retry["completed_at"] = (
                    run.completed_at.isoformat() if run.completed_at else None
                )
                aggregate["judgment_retry"] = retry
            run.aggregate_result = aggregate
            await session.flush()
            await capture_evidence_revision(
                session,
                run,
                reason="aggregation_completed",
            )


class IntegrityEvaluationRunWorker(GovernedEvaluationRunWorker):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(
            session_factory,
            settings=settings,
            worker_id=worker_id,
        )
        self._processor = IntegrityEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = ["IntegrityEvaluationRunProcessor", "IntegrityEvaluationRunWorker"]
