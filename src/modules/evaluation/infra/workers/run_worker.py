from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
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
from modules.evaluation.application.scoring import (
    calculate_trial_score,
    evaluate_deterministic_checks,
)
from modules.evaluation.domain.enums import (
    EvaluationCheckStatus,
    EvaluationRunStatus,
    EvaluationTrialStatus,
    QualificationStatus,
)
from modules.evaluation.infra.database.models import (
    EvaluationCheckResultModel,
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
    ReleaseQualificationModel,
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
        if state is None:
            return None
        trial = state[0]
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is not None and run.lease_owner:
                run.lease_expires_at = _utc_now() + timedelta(minutes=30)
            row = await session.get(EvaluationTrialModel, trial.id, with_for_update=True)
            if row is not None:
                row.attempt = int(row.attempt or 0) + 1
        return state

    async def _execute_trial(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
        suite: EvaluationSuiteVersionModel,
    ) -> None:
        try:
            await self._ensure_not_cancelled(trial.evaluation_run_id)
            persisted_metrics = trial.metrics or {}
            if trial.output_payload is not None and persisted_metrics.get("runtime_completed"):
                output = trial.output_payload
                metrics = persisted_metrics
                agent_run_id = trial.agent_run_id
                network_execution_id = trial.network_execution_id
                trace_id = trial.root_trace_id
            elif target.target_type == "agent":
                output, metrics, agent_run_id, trace_id = await self._execute_agent(
                    trial, target, case
                )
                network_execution_id = None
                await self._persist_runtime_evidence(
                    trial=trial,
                    output=output,
                    metrics=metrics,
                    agent_run_id=agent_run_id,
                    network_execution_id=None,
                    trace_id=trace_id,
                )
            else:
                output, metrics, network_execution_id, trace_id = await self._execute_network(
                    trial, target, case
                )
                agent_run_id = None
                await self._persist_runtime_evidence(
                    trial=trial,
                    output=output,
                    metrics=metrics,
                    agent_run_id=None,
                    network_execution_id=network_execution_id,
                    trace_id=trace_id,
                )

            deterministic = evaluate_deterministic_checks(
                case.expected_contract,
                output=output,
                metrics=metrics,
                suite_checks=suite.deterministic_checks or {},
            )
            await self._mark_judge_started(trial.id)
            async with self._session_factory() as judge_session:
                judge = await self._judge.judge(
                    judge_session,
                    project_id=trial.project_id,
                    provider_model_id=suite.judge_provider_model_id,
                    rubric=suite.rubric or {},
                    judge_config=suite.judge_config or {},
                    case_payload={
                        "name": case.name,
                        "input": case.input_payload,
                        "initial_context": case.initial_context,
                        "expected_contract": case.expected_contract,
                        "severity": case.severity,
                        "weight": case.weight,
                        "blocking": case.blocking,
                    },
                    target_output=output,
                    operational_evidence=metrics,
                )
            calculation = (
                calculate_trial_score(
                    judge_result=judge.structured_result,
                    deterministic=deterministic,
                    case_minimum=float(
                        (case.expected_contract or {}).get("minimum_score", 70)
                    ),
                    judge_weight=float((suite.rubric or {}).get("judge_weight", 4)),
                    case_blocking=bool(case.blocking),
                )
                if judge.structured_result is not None
                else None
            )
            await self._persist_final_result(
                trial=trial,
                case=case,
                output=output,
                metrics=metrics,
                deterministic=deterministic,
                judge=judge,
                calculation=calculation,
                agent_run_id=agent_run_id,
                network_execution_id=network_execution_id,
                trace_id=trace_id,
            )
        except EvaluationRuntimeCancelled as exc:
            await self._mark_trial_cancelled(trial.id, str(exc))
        except Exception as exc:
            async with self._session_factory() as session, session.begin():
                persisted = await session.get(
                    EvaluationTrialModel,
                    trial.id,
                    with_for_update=True,
                )
                if persisted is not None:
                    persisted.status = EvaluationTrialStatus.FAILED.value
                    persisted.failure_code = type(exc).__name__
                    persisted.failure_detail = str(exc)
                    persisted.completed_at = _utc_now()

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

    async def _persist_runtime_evidence(
        self,
        *,
        trial: EvaluationTrialModel,
        output: dict[str, Any],
        metrics: dict[str, Any],
        agent_run_id: UUID | None,
        network_execution_id: UUID | None,
        trace_id: UUID | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial.id, with_for_update=True)
            if row is None:
                return
            row.output_payload = output
            row.metrics = {**metrics, "runtime_completed": True}
            row.agent_run_id = agent_run_id
            row.network_execution_id = network_execution_id
            row.root_trace_id = trace_id
            row.runtime_completed_at = _utc_now()
            row.status = EvaluationTrialStatus.JUDGING.value

    async def _mark_judge_started(self, trial_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial_id, with_for_update=True)
            if row is not None:
                row.status = EvaluationTrialStatus.JUDGING.value
                row.judge_started_at = _utc_now()

    async def _persist_final_result(
        self,
        *,
        trial: EvaluationTrialModel,
        case: EvaluationTestCaseModel,
        output: dict[str, Any],
        metrics: dict[str, Any],
        deterministic: list[Any],
        judge: Any,
        calculation: dict[str, Any] | None,
        agent_run_id: UUID | None,
        network_execution_id: UUID | None,
        trace_id: UUID | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial.id, with_for_update=True)
            if row is None:
                return
            await session.execute(
                delete(EvaluationCheckResultModel).where(
                    EvaluationCheckResultModel.evaluation_trial_id == trial.id
                )
            )
            await session.execute(
                delete(EvaluatorModelCallModel).where(
                    EvaluatorModelCallModel.evaluation_trial_id == trial.id
                )
            )
            session.add_all(
                [
                    EvaluationCheckResultModel(
                        evaluation_trial_id=trial.id,
                        project_id=trial.project_id,
                        evaluator_key=item.key,
                        evaluator_type="deterministic",
                        dimension=item.dimension,
                        status=item.status,
                        score=item.score,
                        weight=item.weight,
                        blocking=item.blocking,
                        reason=item.reason,
                        evidence=item.evidence,
                    )
                    for item in deterministic
                ]
            )
            session.add(
                EvaluatorModelCallModel(
                    evaluation_run_id=trial.evaluation_run_id,
                    evaluation_trial_id=trial.id,
                    project_id=trial.project_id,
                    provider_model_id=judge.provider_model_id,
                    provider_credential_id=judge.provider_credential_id,
                    provider=judge.provider,
                    model=judge.model,
                    judge_config_hash=judge.judge_config_hash,
                    rubric_hash=judge.rubric_hash,
                    status=judge.status,
                    input_tokens=judge.input_tokens,
                    output_tokens=judge.output_tokens,
                    cost_usd=judge.cost_usd,
                    cost_status=judge.cost_status,
                    cost_reason=judge.cost_reason,
                    pricing_snapshot=judge.pricing_snapshot,
                    latency_ms=judge.latency_ms,
                    structured_result=judge.structured_result,
                    error=judge.error,
                    started_at=judge.started_at,
                    completed_at=judge.completed_at,
                )
            )
            if calculation is None:
                row.status = EvaluationTrialStatus.INCONCLUSIVE.value
                row.failure_code = "judge_failed"
                row.failure_detail = (
                    judge.error or "Evaluator Model returned no valid judgment"
                )
                row.score = None
                row.passed = None
                blocking_failures: list[Any] = []
                warnings: list[Any] = []
            else:
                blocking_failures = calculation["blocking_failures"]
                warnings = calculation["warnings"]
                row.status = EvaluationTrialStatus.COMPLETED.value
                row.score = calculation["score"]
                row.passed = calculation["passed"]
                for dimension, raw_score in (
                    judge.structured_result.get("dimensions") or {}
                ).items():
                    try:
                        dimension_score = float(raw_score)
                    except (TypeError, ValueError):
                        continue
                    session.add(
                        EvaluationCheckResultModel(
                            evaluation_trial_id=trial.id,
                            project_id=trial.project_id,
                            evaluator_key=f"llm:{dimension}",
                            evaluator_type="llm",
                            dimension=str(dimension),
                            status=(
                                EvaluationCheckStatus.PASSED.value
                                if dimension_score
                                >= float(
                                    (case.expected_contract or {}).get(
                                        "minimum_score", 70
                                    )
                                )
                                else EvaluationCheckStatus.FAILED.value
                            ),
                            score=dimension_score,
                            weight=1.0,
                            blocking=False,
                            reason=judge.structured_result.get("summary"),
                            evidence={"judge": judge.structured_result},
                        )
                    )
            row.agent_run_id = agent_run_id
            row.network_execution_id = network_execution_id
            row.root_trace_id = trace_id
            row.output_payload = output
            row.metrics = {
                **metrics,
                "runtime_completed": True,
                "judge_cost_usd": judge.cost_usd,
                "judge_latency_ms": judge.latency_ms,
                "checks": {
                    "critical_failures": len(blocking_failures),
                    "warning_count": len(warnings),
                },
            }
            row.judge_completed_at = _utc_now()
            row.completed_at = _utc_now()

    async def _aggregate(self, run_id: UUID) -> None:
        preserved: dict[str, Any] = {}
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is not None and isinstance(run.aggregate_result, dict):
                preserved = {
                    key: run.aggregate_result[key]
                    for key in ("_request", "preflight")
                    if key in run.aggregate_result
                }
            await session.execute(
                delete(ReleaseQualificationModel).where(
                    ReleaseQualificationModel.evaluation_run_id == run_id
                )
            )
        await super()._aggregate(run_id)
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return
            aggregate = {**preserved, **(run.aggregate_result or {})}
            comparison = (
                aggregate.get("comparison")
                if isinstance(aggregate.get("comparison"), dict)
                else None
            )
            if comparison is not None and comparison.get("policy_passed") is False:
                run.qualification_status = QualificationStatus.NOT_QUALIFIED.value
                qualification = (
                    aggregate.get("qualification")
                    if isinstance(aggregate.get("qualification"), dict)
                    else {}
                )
                aggregate["qualification"] = {
                    **qualification,
                    "qualification_status": QualificationStatus.NOT_QUALIFIED.value,
                }
                rows = list(
                    (
                        await session.scalars(
                            select(ReleaseQualificationModel).where(
                                ReleaseQualificationModel.evaluation_run_id == run.id
                            )
                        )
                    ).all()
                )
                for row in rows:
                    row.status = QualificationStatus.NOT_QUALIFIED.value
                    row.summary = aggregate["qualification"]
            run.aggregate_result = aggregate

    async def _mark_trial_cancelled(self, trial_id: UUID, detail: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial_id, with_for_update=True)
            if row is not None:
                row.status = EvaluationTrialStatus.FAILED.value
                row.failure_code = "evaluation_cancelled"
                row.failure_detail = detail
                row.completed_at = _utc_now()

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
        super().__init__(session_factory, settings=settings, worker_id=worker_id)
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
                    EvaluationRunModel.lease_expires_at.is_(None)
                    | (EvaluationRunModel.lease_expires_at < now),
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
