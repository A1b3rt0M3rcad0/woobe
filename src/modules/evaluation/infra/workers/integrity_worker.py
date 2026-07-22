from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.evidence_revision_snapshot import (
    capture_evidence_revision,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.workers.governed_worker import (
    GovernedEvaluationRunProcessor,
    GovernedEvaluationRunWorker,
)
from shared.infra.config import Settings


class IntegrityEvaluationRunProcessor(GovernedEvaluationRunProcessor):
    """Keep unavailable metrics distinct from zero and freeze each revision."""

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
