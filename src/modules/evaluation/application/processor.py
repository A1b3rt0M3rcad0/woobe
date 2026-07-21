from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.evaluation.application.scoring import (
    aggregate_evaluation,
    build_estimate,
    evaluate_deterministic_checks,
)
from modules.evaluation.domain.enums import (
    EvaluationCheckStatus,
    EvaluationRunStatus,
    EvaluationTargetSide,
    EvaluationTrialStatus,
)
from modules.evaluation.infra.database.models import (
    EstimateRunModel,
    EvaluationCheckResultModel,
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
    ReleaseQualificationModel,
)
from modules.evaluation.infra.judge import EvaluatorModelGateway
from modules.network.application.agent_invoker import ProjectRAIAgentInvoker
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkMessageModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
)
from modules.observability.infra.database.models import TraceModel
from shared.infra.config import Settings
from shared.infra.errors import ValidationError


_TERMINAL_NETWORK_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _message_from_case(case: EvaluationTestCaseModel) -> str:
    payload = case.input_payload or {}
    value = payload.get("message") or payload.get("input") or payload.get("prompt")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Evaluation case {case.name} has no message input")
    return value.strip()


def _trial_payload(trial: EvaluationTrialModel, target: EvaluationTargetModel) -> dict[str, Any]:
    metrics = trial.metrics or {}
    checks = metrics.get("checks") if isinstance(metrics.get("checks"), dict) else {}
    return {
        "id": str(trial.id),
        "pair_key": trial.pair_key,
        "side": target.side,
        "status": trial.status,
        "score": trial.score,
        "passed": trial.passed,
        "metrics": metrics,
        "critical_failures": int(checks.get("critical_failures") or 0),
        "warning_count": int(checks.get("warning_count") or 0),
    }


class EvaluationRunProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or Settings()
        self._judge = EvaluatorModelGateway(self._settings)
        self._agent_invoker = ProjectRAIAgentInvoker(
            session_factory,
            settings=self._settings,
            http_executor=get_http_tool_executor(),
        )

    async def process(self, run_id: UUID) -> None:
        await self._prepare_trials(run_id)
        while True:
            state = await self._next_trial(run_id)
            if state is None:
                break
            trial, target, case, suite = state
            await self._execute_trial(trial, target, case, suite)
        await self._aggregate(run_id)

    async def _prepare_trials(self, run_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return
            if run.cancel_requested_at is not None:
                run.status = EvaluationRunStatus.CANCELLED.value
                run.completed_at = _utc_now()
                return
            run.status = EvaluationRunStatus.SNAPSHOTTING.value
            run.started_at = run.started_at or _utc_now()
            suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
            if suite is None or suite.project_id != run.project_id:
                raise ValidationError("Evaluation Suite version not found")
            existing_count = await session.scalar(
                select(func.count(EvaluationTrialModel.id)).where(
                    EvaluationTrialModel.evaluation_run_id == run.id
                )
            )
            if existing_count:
                run.status = EvaluationRunStatus.EXECUTING.value
                return
            cases = list(
                (
                    await session.scalars(
                        select(EvaluationTestCaseModel)
                        .where(
                            EvaluationTestCaseModel.dataset_version_id
                            == suite.dataset_version_id,
                            EvaluationTestCaseModel.project_id == run.project_id,
                        )
                        .order_by(EvaluationTestCaseModel.position)
                    )
                ).all()
            )
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel)
                        .where(EvaluationTargetModel.evaluation_run_id == run.id)
                        .order_by(EvaluationTargetModel.side)
                    )
                ).all()
            )
            if not cases:
                raise ValidationError("Evaluation Dataset version has no Test Cases")
            if not targets:
                raise ValidationError("Evaluation Run has no resolved targets")

            rng = random.Random(run.randomization_seed)
            order = 0
            trials: list[EvaluationTrialModel] = []
            for case in cases:
                for repetition in range(1, run.repetitions + 1):
                    pair_targets = list(targets)
                    rng.shuffle(pair_targets)
                    for target in pair_targets:
                        order += 1
                        trials.append(
                            EvaluationTrialModel(
                                evaluation_run_id=run.id,
                                evaluation_target_id=target.id,
                                test_case_id=case.id,
                                project_id=run.project_id,
                                repetition=repetition,
                                pair_key=f"{case.id}:{repetition}",
                                execution_order=order,
                                status=EvaluationTrialStatus.PENDING.value,
                            )
                        )
            session.add_all(trials)
            run.status = EvaluationRunStatus.EXECUTING.value

    async def _next_trial(
        self,
        run_id: UUID,
    ) -> tuple[
        EvaluationTrialModel,
        EvaluationTargetModel,
        EvaluationTestCaseModel,
        EvaluationSuiteVersionModel,
    ] | None:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return None
            if run.cancel_requested_at is not None:
                run.status = EvaluationRunStatus.CANCELLED.value
                run.completed_at = _utc_now()
                return None
            trial = await session.scalar(
                select(EvaluationTrialModel)
                .where(
                    EvaluationTrialModel.evaluation_run_id == run.id,
                    EvaluationTrialModel.status == EvaluationTrialStatus.PENDING.value,
                )
                .order_by(EvaluationTrialModel.execution_order)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if trial is None:
                return None
            target = await session.get(EvaluationTargetModel, trial.evaluation_target_id)
            case = await session.get(EvaluationTestCaseModel, trial.test_case_id)
            suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
            if target is None or case is None or suite is None:
                trial.status = EvaluationTrialStatus.BLOCKED.value
                trial.failure_code = "evaluation_reference_missing"
                trial.failure_detail = "Evaluation target, case or Suite version is unavailable"
                trial.completed_at = _utc_now()
                return None
            trial.status = EvaluationTrialStatus.EXECUTING.value
            trial.started_at = _utc_now()
            await session.flush()
            session.expunge(trial)
            session.expunge(target)
            session.expunge(case)
            session.expunge(suite)
            return trial, target, case, suite

    async def _execute_trial(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
        suite: EvaluationSuiteVersionModel,
    ) -> None:
        try:
            if target.target_type == "agent":
                output, metrics, runtime_id, trace_id = await self._execute_agent(
                    trial,
                    target,
                    case,
                )
                agent_run_id = runtime_id
                network_execution_id = None
            else:
                output, metrics, runtime_id, trace_id = await self._execute_network(
                    trial,
                    target,
                    case,
                )
                agent_run_id = None
                network_execution_id = runtime_id

            deterministic = evaluate_deterministic_checks(
                case.expected_contract,
                output=output,
                metrics=metrics,
            )
            blocking_failures = [
                item for item in deterministic if item.blocking and item.status == "failed"
            ]
            warnings = [
                item for item in deterministic if not item.blocking and item.status == "failed"
            ]

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
                    },
                    target_output=output,
                    operational_evidence=metrics,
                )

            await self._persist_trial_result(
                trial=trial,
                target=target,
                case=case,
                output=output,
                metrics=metrics,
                deterministic=deterministic,
                judge=judge,
                blocking_failures=blocking_failures,
                warnings=warnings,
                agent_run_id=agent_run_id,
                network_execution_id=network_execution_id,
                trace_id=trace_id,
            )
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
    ) -> tuple[dict[str, Any], dict[str, Any], UUID, UUID | None]:
        started = _utc_now()
        message = _message_from_case(case)
        release_id = target.agent_release_id
        snapshot_override = target.snapshot if target.source_type == "draft" else None
        result = await self._agent_invoker.invoke(
            project_id=trial.project_id,
            agent_id=target.entity_id,
            release_id=release_id,
            snapshot_override=snapshot_override,
            message=message,
            agent_session_id=None,
            execution_context="playground",
            internal_tools=[],
            network_context={},
        )
        elapsed_ms = round((_utc_now() - started).total_seconds() * 1000)
        usage = result.usage or {}
        runtime_id = uuid4()
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
        }
        return output, metrics, runtime_id, result.trace_id

    async def _execute_network(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
    ) -> tuple[dict[str, Any], dict[str, Any], UUID, UUID | None]:
        message = _message_from_case(case)
        execution_id = uuid4()
        session_id = uuid4()
        event_id = uuid4()
        snapshot = target.snapshot or {}
        definition = snapshot.get("definition")
        bindings = snapshot.get("resolved_bindings")
        draft_revision = snapshot.get("draft_revision") if target.source_type == "draft" else None
        network_version_id = target.network_version_id
        environment = "draft" if target.source_type == "draft" else (
            "staging" if target.source_type == "staging" else "production"
        )
        async with self._session_factory() as session, session.begin():
            network_session = NetworkSessionModel(
                id=session_id,
                network_id=target.entity_id,
                network_version_id=network_version_id,
                project_id=trial.project_id,
                environment=environment,
                title=f"Evaluation {trial.evaluation_run_id}",
                tenant_id="evaluation",
                user_id=None,
                external_session_id=f"evaluation:{trial.id}",
                status="active",
            )
            execution = NetworkExecutionModel(
                id=execution_id,
                network_id=target.entity_id,
                network_version_id=network_version_id,
                network_session_id=session_id,
                project_id=trial.project_id,
                input_message=message,
                draft_revision=draft_revision,
                definition_snapshot=definition if target.source_type == "draft" else None,
                resolved_bindings_snapshot=bindings if target.source_type == "draft" else None,
                status="queued",
                idempotency_key=f"evaluation:{trial.id}",
                last_event_sequence=1,
            )
            session.add_all(
                [
                    network_session,
                    execution,
                    NetworkMessageModel(
                        network_session_id=session_id,
                        network_execution_id=execution_id,
                        project_id=trial.project_id,
                        role="user",
                        content=message,
                        data={"run_purpose": "evaluation", "evaluation_trial_id": str(trial.id)},
                    ),
                    NetworkExecutionEventModel(
                        id=event_id,
                        network_execution_id=execution_id,
                        network_session_id=session_id,
                        sequence=1,
                        event_type="execution_accepted",
                        payload={
                            "status": "queued",
                            "environment": environment,
                            "run_purpose": "evaluation",
                            "evaluation_run_id": str(trial.evaluation_run_id),
                            "evaluation_trial_id": str(trial.id),
                            "target_side": target.side,
                            "composition_hash": target.composition_hash,
                        },
                    ),
                    NetworkOutboxEventModel(
                        aggregate_type="network_execution",
                        aggregate_id=execution_id,
                        event_type="network.execution.requested.v1",
                        event_version=1,
                        routing_key=f"network.execution.{environment}.requested.v1",
                        payload={
                            "execution_id": str(execution_id),
                            "run_purpose": "evaluation",
                            "evaluation_run_id": str(trial.evaluation_run_id),
                            "evaluation_trial_id": str(trial.id),
                        },
                        metadata_=None,
                        idempotency_key=f"evaluation-network-execution:{trial.id}",
                        correlation_id=execution_id,
                        causation_id=None,
                        status="pending",
                    ),
                ]
            )

        timeout_seconds = int((target.snapshot or {}).get("timeout_seconds") or 360)
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        execution: NetworkExecutionModel | None = None
        while asyncio.get_running_loop().time() < deadline:
            async with self._session_factory() as session:
                execution = await session.get(NetworkExecutionModel, execution_id)
                if execution is not None and execution.status in _TERMINAL_NETWORK_STATUSES:
                    break
            await asyncio.sleep(0.5)
        if execution is None or execution.status not in _TERMINAL_NETWORK_STATUSES:
            raise TimeoutError("Network Evaluation Trial exceeded its timeout")
        if execution.status != "completed":
            raise RuntimeError(
                execution.failure_detail
                or execution.failure_code
                or f"Network execution ended as {execution.status}"
            )

        async with self._session_factory() as session:
            invocation_count = await session.scalar(
                select(func.count(NetworkInvocationModel.id)).where(
                    NetworkInvocationModel.network_execution_id == execution_id
                )
            )
            trace_rows = list(
                (
                    await session.scalars(
                        select(TraceModel).where(
                            TraceModel.network_execution_id == execution_id
                        )
                    )
                ).all()
            )
        costs = [float(item.total_cost_usd) for item in trace_rows if item.total_cost_usd is not None]
        cost_usd = sum(costs) if costs else None
        latency_ms = None
        if execution.started_at and execution.completed_at:
            latency_ms = round(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
        output = {
            "answer": execution.output_message or "",
            "parsed_output": None,
            "output_parse_error": None,
            "tool_calls": [],
            "sources": [],
        }
        metrics = {
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "agent_run_count": int(invocation_count or 0),
            "tool_call_count": 0,
            "fallback_used": any(item.fallback_used for item in trace_rows),
            "run_purpose": "evaluation",
            "network_execution_status": execution.status,
        }
        return output, metrics, execution_id, execution.root_trace_id

    async def _persist_trial_result(
        self,
        *,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
        output: dict[str, Any],
        metrics: dict[str, Any],
        deterministic: list[Any],
        judge: Any,
        blocking_failures: list[Any],
        warnings: list[Any],
        agent_run_id: UUID | None,
        network_execution_id: UUID | None,
        trace_id: UUID | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            persisted = await session.get(
                EvaluationTrialModel,
                trial.id,
                with_for_update=True,
            )
            if persisted is None:
                return
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
            if judge.structured_result is None:
                persisted.status = EvaluationTrialStatus.INCONCLUSIVE.value
                persisted.failure_code = "judge_failed"
                persisted.failure_detail = judge.error or "Evaluator Model returned no valid judgment"
                persisted.score = None
                persisted.passed = None
            else:
                judge_score = float(judge.structured_result["score"])
                deterministic_scores = [
                    float(item.score)
                    for item in deterministic
                    if item.score is not None
                ]
                score_components = [judge_score, *deterministic_scores]
                final_score = sum(score_components) / len(score_components)
                judgment_passed = judge.structured_result["status"] in {
                    "passed",
                    "passed_with_warnings",
                }
                case_minimum = float(
                    (case.expected_contract or {}).get("minimum_score", 70)
                )
                persisted.status = EvaluationTrialStatus.COMPLETED.value
                persisted.score = final_score
                persisted.passed = (
                    judgment_passed
                    and not blocking_failures
                    and final_score >= case_minimum
                )
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
                                if dimension_score >= case_minimum
                                else EvaluationCheckStatus.FAILED.value
                            ),
                            score=dimension_score,
                            weight=1.0,
                            blocking=False,
                            reason=judge.structured_result.get("summary"),
                            evidence={"judge": judge.structured_result},
                        )
                    )
            persisted.agent_run_id = agent_run_id
            persisted.network_execution_id = network_execution_id
            persisted.root_trace_id = trace_id
            persisted.output_payload = output
            persisted.metrics = {
                **metrics,
                "judge_cost_usd": judge.cost_usd,
                "checks": {
                    "critical_failures": len(blocking_failures),
                    "warning_count": len(warnings),
                },
            }
            persisted.completed_at = _utc_now()

    async def _aggregate(self, run_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return
            if run.status == EvaluationRunStatus.CANCELLED.value:
                return
            run.status = EvaluationRunStatus.AGGREGATING.value
            suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
            if suite is None:
                raise ValidationError("Evaluation Suite version not found")
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel)
                        .where(EvaluationTrialModel.evaluation_run_id == run.id)
                        .order_by(EvaluationTrialModel.execution_order)
                    )
                ).all()
            )
            targets = {
                item.id: item
                for item in (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            }
            payloads = [
                _trial_payload(item, targets[item.evaluation_target_id])
                for item in trials
                if item.evaluation_target_id in targets
            ]
            complete_aggregate = aggregate_evaluation(
                payloads,
                suite.acceptance_policy,
            )
            qualification_side = (
                EvaluationTargetSide.CANDIDATE.value
                if run.candidate_target_id is not None
                else EvaluationTargetSide.SINGLE.value
            )
            qualification_payloads = [
                item for item in payloads if item["side"] == qualification_side
            ]
            qualification = aggregate_evaluation(
                qualification_payloads,
                suite.acceptance_policy,
            )
            run.qualification_status = qualification["qualification_status"]
            run.overall_score = qualification["overall_score"]
            run.pass_rate = qualification["pass_rate"]
            run.aggregate_result = {
                **complete_aggregate,
                "qualification": qualification,
            }
            model_call_cost = await session.scalar(
                select(func.sum(EvaluatorModelCallModel.cost_usd)).where(
                    EvaluatorModelCallModel.evaluation_run_id == run.id
                )
            )
            target_costs = [
                float((item.metrics or {}).get("cost_usd"))
                for item in trials
                if (item.metrics or {}).get("cost_usd") is not None
            ]
            run.measured_total_cost = sum(target_costs) + float(model_call_cost or 0)
            incomplete = any(
                item.status
                not in {
                    EvaluationTrialStatus.COMPLETED.value,
                    EvaluationTrialStatus.INCONCLUSIVE.value,
                }
                for item in trials
            )
            run.status = (
                EvaluationRunStatus.PARTIALLY_COMPLETED.value
                if incomplete
                else EvaluationRunStatus.COMPLETED.value
            )
            run.completed_at = _utc_now()
            run.lease_owner = None
            run.lease_expires_at = None

            target = targets.get(run.candidate_target_id or next(iter(targets), None))
            if target is not None:
                qualification_record = ReleaseQualificationModel(
                    project_id=run.project_id,
                    target_type=target.target_type,
                    entity_id=target.entity_id,
                    target_snapshot_hash=target.snapshot_hash,
                    agent_release_id=target.agent_release_id,
                    network_version_id=target.network_version_id,
                    suite_version_id=suite.id,
                    dataset_version_id=suite.dataset_version_id,
                    evaluation_run_id=run.id,
                    status=run.qualification_status or "inconclusive",
                    score=run.overall_score,
                    pass_rate=run.pass_rate,
                    critical_failures=int(qualification["critical_failures"]),
                    summary=qualification,
                )
                session.add(qualification_record)

            volume = int((suite.estimate_defaults or {}).get("volume", 10_000))
            existing_estimate_count = await session.scalar(
                select(func.count(EstimateRunModel.id)).where(
                    EstimateRunModel.evaluation_run_id == run.id
                )
            )
            if not existing_estimate_count:
                for target_id, evaluation_target in targets.items():
                    target_trials = [
                        item
                        for item in payloads
                        if item["side"] == evaluation_target.side
                        and item["status"] == EvaluationTrialStatus.COMPLETED.value
                    ]
                    estimate = build_estimate(
                        values=target_trials,
                        volume=volume,
                        target_type=evaluation_target.target_type,
                    )
                    session.add(
                        EstimateRunModel(
                            project_id=run.project_id,
                            evaluation_run_id=run.id,
                            target_id=target_id,
                            volume_unit="runs_per_month",
                            volume=volume,
                            assumptions={
                                "projection_method": "observed_trial_distribution",
                                "run_purpose": "evaluation",
                            },
                            observation_summary=estimate["observation_summary"],
                            price_snapshot=None,
                            scenarios=estimate["scenarios"],
                            confidence=estimate["confidence"],
                            limitations=estimate["limitations"],
                            created_by=run.requested_by,
                        )
                    )


class EvaluationRunWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._processor = EvaluationRunProcessor(
            session_factory,
            settings=settings,
        )
        self._worker_id = worker_id or f"evaluation-worker:{uuid4()}"

    async def run(self) -> None:
        run_id = await self._claim()
        if run_id is None:
            return
        try:
            await self._processor.process(run_id)
        except Exception as exc:
            async with self._session_factory() as session, session.begin():
                run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
                if run is not None:
                    run.status = EvaluationRunStatus.FAILED.value
                    run.failure_code = type(exc).__name__
                    run.failure_detail = str(exc)
                    run.completed_at = _utc_now()
                    run.lease_owner = None
                    run.lease_expires_at = None

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
