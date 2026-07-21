from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.processor import (
    EvaluationRunProcessor,
    EvaluationRunWorker,
    _message_from_case,
    _utc_now,
)
from modules.evaluation.domain.enums import (
    EvaluationRunStatus,
    EvaluationTrialStatus,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
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

    async def _execute_agent(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
    ) -> tuple[dict[str, Any], dict[str, Any], None, UUID | None]:
        started = _utc_now()
        result = await self._agent_invoker.invoke(
            project_id=trial.project_id,
            agent_id=target.entity_id,
            release_id=target.agent_release_id,
            snapshot_override=target.snapshot if target.source_type == "draft" else None,
            message=_message_from_case(case),
            agent_session_id=None,
            execution_context="playground",
            internal_tools=[],
            network_context={
                "run_purpose": "evaluation",
                "evaluation_run_id": str(trial.evaluation_run_id),
                "evaluation_trial_id": str(trial.id),
                "comparison_pair_id": trial.pair_key,
                "target_side": target.side,
            },
        )
        elapsed_ms = round((_utc_now() - started).total_seconds() * 1000)
        usage = result.usage or {}
        output = {
            "answer": result.answer,
            "parsed_output": result.parsed_output,
            "output_parse_error": result.output_parse_error,
            "tool_calls": result.tool_calls,
            "sources": result.sources,
        }
        metrics = {
            "latency_ms": elapsed_ms,
            "cost_usd": usage.get("cost_usd"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "tool_call_count": len(result.tool_calls),
            "source_count": len(result.sources),
            "fallback_used": False,
            "agent_run_count": 1,
            "provider": result.provider,
            "model": result.model,
            "run_purpose": "evaluation",
            "evaluation_run_id": str(trial.evaluation_run_id),
            "evaluation_trial_id": str(trial.id),
            "comparison_pair_id": trial.pair_key,
            "target_side": target.side,
        }
        # Direct Agent execution does not yet have a canonical persisted AgentRun row.
        # The Evaluation Trial and real Trace are the stable identities; never expose a
        # synthetic UUID as if it were an operational Run.
        return output, metrics, None, result.trace_id

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
