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
from modules.evaluation.application.runtime_gateway import (
    EvaluationNetworkRuntimeGateway,
    EvaluationRuntimeCancelled,
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
from modules.observability.infra.database.models import TraceModel
from shared.infra.config import Settings


class ResumableEvaluationRunProcessor(EvaluationRunProcessor):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(session_factory, settings=settings)
        self._network_gateway = EvaluationNetworkRuntimeGateway(session_factory)

    async def _prepare_trials(self, run_id: UUID) -> None:
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
                    EvaluationTrialModel.network_execution_id.is_(None),
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
        await self._ensure_not_cancelled(trial.evaluation_run_id)
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
                "initial_context": case.initial_context,
            },
        )
        elapsed_ms = round((_utc_now() - started).total_seconds() * 1000)
        usage = result.usage or {}
        trace = None
        if result.trace_id is not None:
            async with self._session_factory() as session:
                trace = await session.get(TraceModel, result.trace_id)
        output = {
            "answer": result.answer,
            "parsed_output": result.parsed_output,
            "output_parse_error": result.output_parse_error,
            "tool_calls": result.tool_calls or [],
            "sources": result.sources or [],
        }
        metrics = {
            "latency_ms": (
                trace.total_latency_ms
                if trace is not None and trace.total_latency_ms is not None
                else elapsed_ms
            ),
            "cost_usd": (
                trace.total_cost_usd
                if trace is not None and trace.total_cost_usd is not None
                else usage.get("cost_usd")
            ),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "tool_call_count": len(result.tool_calls or []),
            "source_count": len(result.sources or []),
            "fallback_used": bool(trace.fallback_used) if trace is not None else None,
            "agent_run_count": 1,
            "provider": result.provider,
            "model": result.model,
            "pricing_coverage": (
                "complete"
                if trace is not None and trace.total_cost_usd is not None
                else "partial"
                if usage.get("cost_usd") is not None
                else "unknown"
            ),
            "run_purpose": "evaluation",
            "evaluation_run_id": str(trial.evaluation_run_id),
            "evaluation_trial_id": str(trial.id),
            "comparison_pair_id": trial.pair_key,
            "target_side": target.side,
            "case_weight": float(case.weight or 1.0),
            "production_frequency": case.production_frequency,
            "case_severity": case.severity,
            "case_blocking": bool(case.blocking),
        }
        return output, metrics, None, result.trace_id

    async def _execute_network(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
    ) -> tuple[dict[str, Any], dict[str, Any], UUID, UUID | None]:
        evidence = await self._network_gateway.execute(
            evaluation_run_id=trial.evaluation_run_id,
            evaluation_trial_id=trial.id,
            pair_key=trial.pair_key,
            target_side=target.side,
            project_id=trial.project_id,
            target=target,
            message=_message_from_case(case),
            initial_context=case.initial_context,
        )
        metrics = {
            **evidence.metrics,
            "evaluation_run_id": str(trial.evaluation_run_id),
            "evaluation_trial_id": str(trial.id),
            "comparison_pair_id": trial.pair_key,
            "target_side": target.side,
            "case_weight": float(case.weight or 1.0),
            "production_frequency": case.production_frequency,
            "case_severity": case.severity,
            "case_blocking": bool(case.blocking),
        }
        return (
            evidence.output,
            metrics,
            evidence.network_execution_id,
            evidence.root_trace_id,
        )

    async def _aggregate(self, run_id: UUID) -> None:
        preserved: dict[str, Any] = {}
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is not None and isinstance(run.aggregate_result, dict):
                preserved = {
                    key: run.aggregate_result[key]
                    for key in ("_request", "preflight")
                    if key in run.aggregate_result
                }
        await super()._aggregate(run_id)
        if preserved:
            async with self._session_factory() as session, session.begin():
                run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
                if run is not None:
                    run.aggregate_result = {
                        **preserved,
                        **(run.aggregate_result or {}),
                    }

    async def _ensure_not_cancelled(self, run_id: UUID) -> None:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is not None and run.cancel_requested_at is not None:
                raise EvaluationRuntimeCancelled("Evaluation Run was cancelled")


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
