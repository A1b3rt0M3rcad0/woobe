from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.runtime_gateway import EvaluationRuntimeCancelled
from modules.evaluation.domain.enums import EvaluationRunStatus, EvaluationTrialStatus
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.workers.outcome_worker import (
    OutcomeAwareEvaluationRunProcessor,
    OutcomeAwareEvaluationRunWorker,
)
from shared.infra.config import Settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConcurrentOutcomeAwareEvaluationRunProcessor(OutcomeAwareEvaluationRunProcessor):
    """Runs different pair groups concurrently while serializing each pair."""

    async def process(self, run_id: UUID) -> None:
        await self._prepare_trials(run_id)
        parallelism = await self._effective_parallelism(run_id)
        pair_locks: dict[str, asyncio.Lock] = {}
        locks_guard = asyncio.Lock()

        async def worker_loop() -> None:
            while True:
                state = await self._next_trial(run_id)
                if state is None:
                    return
                trial = state[0]
                async with locks_guard:
                    pair_lock = pair_locks.setdefault(trial.pair_key, asyncio.Lock())
                async with pair_lock:
                    await self._execute_trial(*state)

        await asyncio.gather(*(worker_loop() for _ in range(parallelism)))
        if await self._run_cancelled(run_id):
            await self._finalize_cancelled(run_id)
            return
        await self._aggregate(run_id)

    async def _effective_parallelism(self, run_id: UUID) -> int:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return 1
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            request = run.execution_policy or {}
            requested = max(1, min(int(request.get("requested_parallel_pairs") or 3), 5))
            aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
            preflight = aggregate.get("preflight") if isinstance(aggregate.get("preflight"), dict) else {}
            risk_counts = preflight.get("risk_counts") if isinstance(preflight.get("risk_counts"), dict) else {}
            if int(risk_counts.get("medium") or 0) > 0 or int(risk_counts.get("high") or 0) > 0:
                effective = 1
                reason = "side_effecting_tools"
            elif any(item.target_type == "network" for item in targets):
                effective = min(requested, 2)
                reason = "network_runtime_limit"
            else:
                effective = min(requested, 3)
                reason = "agent_runtime_limit"
            run.execution_policy = {
                **request,
                "requested_parallel_pairs": requested,
                "effective_parallel_pairs": effective,
                "reason": reason,
                "pair_members_serialized": True,
            }
            return effective

    async def _mark_judge_started(self, trial_id: UUID) -> None:
        async with self._session_factory() as session:
            trial = await session.get(EvaluationTrialModel, trial_id)
            run = (
                await session.get(EvaluationRunModel, trial.evaluation_run_id)
                if trial is not None
                else None
            )
            if run is not None and run.cancel_requested_at is not None:
                raise EvaluationRuntimeCancelled("Evaluation Run was cancelled before Judge execution")
        await super()._mark_judge_started(trial_id)

    async def _mark_trial_cancelled(self, trial_id: UUID, detail: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial_id, with_for_update=True)
            if row is not None:
                row.status = EvaluationTrialStatus.CANCELLED.value
                row.failure_code = "evaluation_cancelled"
                row.failure_detail = detail[:2000]
                row.score = None
                row.passed = None
                row.completed_at = _now()

    async def _run_cancelled(self, run_id: UUID) -> bool:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            return bool(
                run is not None
                and (
                    run.cancel_requested_at is not None
                    or run.status == EvaluationRunStatus.CANCELLED.value
                )
            )

    async def _finalize_cancelled(self, run_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(EvaluationTrialModel)
                .where(
                    EvaluationTrialModel.evaluation_run_id == run_id,
                    EvaluationTrialModel.status.in_(
                        {
                            EvaluationTrialStatus.PENDING.value,
                            EvaluationTrialStatus.EXECUTING.value,
                            EvaluationTrialStatus.WAITING_RUNTIME.value,
                            EvaluationTrialStatus.JUDGING.value,
                        }
                    ),
                )
                .values(
                    status=EvaluationTrialStatus.CANCELLED.value,
                    failure_code="evaluation_cancelled",
                    failure_detail="Evaluation Run cancelled before Trial completion",
                    score=None,
                    passed=None,
                    completed_at=_now(),
                )
            )
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is not None:
                run.status = EvaluationRunStatus.CANCELLED.value
                run.qualification_status = None
                run.completed_at = _now()
                run.lease_owner = None
                run.lease_expires_at = None
                aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
                run.aggregate_result = {
                    **aggregate,
                    "cancellation": {
                        "cancelled": True,
                        "external_side_effects_may_have_completed": True,
                    },
                }


class ConcurrentOutcomeAwareEvaluationRunWorker(OutcomeAwareEvaluationRunWorker):
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
        self._processor = ConcurrentOutcomeAwareEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = [
    "ConcurrentOutcomeAwareEvaluationRunProcessor",
    "ConcurrentOutcomeAwareEvaluationRunWorker",
]
