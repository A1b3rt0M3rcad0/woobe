from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.processor import (
    EvaluationRunProcessor,
    EvaluationRunWorker,
    _utc_now,
)
from modules.evaluation.domain.enums import (
    EvaluationRunStatus,
    EvaluationTrialStatus,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTrialModel,
)
from shared.infra.config import Settings


class ResumableEvaluationRunProcessor(EvaluationRunProcessor):
    async def _prepare_trials(self, run_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(EvaluationTrialModel)
                .where(
                    EvaluationTrialModel.evaluation_run_id == run_id,
                    EvaluationTrialModel.status.in_(
                        {
                            EvaluationTrialStatus.EXECUTING.value,
                            EvaluationTrialStatus.WAITING_RUNTIME.value,
                            EvaluationTrialStatus.JUDGING.value,
                        }
                    ),
                    EvaluationTrialModel.completed_at.is_(None),
                )
                .values(
                    status=EvaluationTrialStatus.PENDING.value,
                    failure_code=None,
                    failure_detail=None,
                )
            )
        await super()._prepare_trials(run_id)

    async def _next_trial(self, run_id: UUID):
        state = await super()._next_trial(run_id)
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is not None and run.lease_owner:
                run.lease_expires_at = _utc_now() + timedelta(minutes=30)
        return state

    async def _aggregate(self, run_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is not None and run.mode == "absolute":
                target = await session.scalar(
                    select(EvaluationTargetModel).where(
                        EvaluationTargetModel.evaluation_run_id == run.id,
                        EvaluationTargetModel.side == "single",
                    )
                )
                if target is not None:
                    target.side = "candidate"
        await super()._aggregate(run_id)


class ResumableEvaluationRunWorker(EvaluationRunWorker):
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
        self._processor = ResumableEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )

    async def _claim(self) -> UUID | None:
        async with self._session_factory() as session, session.begin():
            now = _utc_now()
            run = await session.scalar(
                select(EvaluationRunModel)
                .where(
                    EvaluationRunModel.status.in_(
                        {
                            EvaluationRunStatus.QUEUED.value,
                            EvaluationRunStatus.SNAPSHOTTING.value,
                            EvaluationRunStatus.EXECUTING.value,
                            EvaluationRunStatus.JUDGING.value,
                            EvaluationRunStatus.AGGREGATING.value,
                            EvaluationRunStatus.CANCEL_REQUESTED.value,
                        }
                    ),
                    (
                        EvaluationRunModel.lease_expires_at.is_(None)
                        | (EvaluationRunModel.lease_expires_at < now)
                    ),
                )
                .order_by(EvaluationRunModel.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if run is None:
                return None
            run.lease_owner = self._worker_id
            run.lease_expires_at = now + timedelta(minutes=30)
            return run.id
