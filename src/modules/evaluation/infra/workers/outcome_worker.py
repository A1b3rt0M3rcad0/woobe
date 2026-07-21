from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.outcome_scoring import (
    evaluate_outcome_check,
    outcome_is_platform_failure,
)
from modules.evaluation.application.runtime_gateway import EvaluationRuntimeCancelled
from modules.evaluation.application.scoring import (
    calculate_trial_score,
    evaluate_deterministic_checks,
)
from modules.evaluation.domain.contracts import classify_runtime_failure
from modules.evaluation.domain.enums import EvaluationTrialStatus
from modules.evaluation.infra.budgeted_judge import BudgetedEvaluatorModelGateway
from modules.evaluation.infra.database.models import (
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.workers.run_worker import (
    ResumableEvaluationRunProcessor,
    ResumableEvaluationRunWorker,
)
from shared.infra.config import Settings


class OutcomeAwareEvaluationRunProcessor(ResumableEvaluationRunProcessor):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(session_factory, settings=settings)
        self._judge = BudgetedEvaluatorModelGateway(settings)

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
            else:
                try:
                    if target.target_type == "agent":
                        output, metrics, agent_run_id, trace_id = await self._execute_agent(
                            trial, target, case
                        )
                        network_execution_id = None
                    else:
                        output, metrics, network_execution_id, trace_id = await self._execute_network(
                            trial, target, case
                        )
                        agent_run_id = None
                    observed_outcome = {
                        "type": "response",
                        "failure_origin": None,
                        "failure_stage": None,
                        "failure_code": None,
                    }
                except EvaluationRuntimeCancelled:
                    raise
                except Exception as exc:
                    observed_outcome = classify_runtime_failure(exc)
                    output = {
                        "answer": "",
                        "parsed_output": None,
                        "output_parse_error": None,
                        "tool_calls": [],
                        "sources": [],
                        "observed_outcome": observed_outcome,
                    }
                    metrics = {
                        "runtime_completed": True,
                        "latency_ms": None,
                        "cost_usd": None,
                        "input_tokens": None,
                        "output_tokens": None,
                        "tool_call_count": 0,
                        "source_count": 0,
                        "fallback_used": None,
                        "agent_run_count": 0,
                        "run_purpose": "evaluation",
                        "evaluation_run_id": str(trial.evaluation_run_id),
                        "evaluation_trial_id": str(trial.id),
                        "comparison_pair_id": trial.pair_key,
                        "target_side": target.side,
                        "case_weight": float(case.weight or 1.0),
                        "production_frequency": case.production_frequency,
                        "case_severity": case.severity,
                        "case_blocking": bool(case.blocking),
                        "observed_outcome": observed_outcome,
                    }
                    agent_run_id = None
                    network_execution_id = None
                    trace_id = None
                output = {**output, "observed_outcome": observed_outcome}
                metrics = {**metrics, "observed_outcome": observed_outcome}
                await self._persist_runtime_evidence(
                    trial=trial,
                    output=output,
                    metrics=metrics,
                    agent_run_id=agent_run_id,
                    network_execution_id=network_execution_id,
                    trace_id=trace_id,
                )

            observed = metrics.get("observed_outcome")
            if isinstance(observed, dict) and observed.get("failure_origin") in {"platform", "cancelled"}:
                await self._persist_inconclusive_outcome(trial.id, observed, output, metrics)
                return

            deterministic = evaluate_deterministic_checks(
                case.expected_contract,
                output=output,
                metrics=metrics,
                suite_checks=suite.deterministic_checks or {},
            )
            deterministic.append(
                evaluate_outcome_check(
                    case_type=getattr(case, "case_type", None) or "success",
                    expected_contract=case.expected_contract,
                    output=output,
                    metrics=metrics,
                )
            )
            if outcome_is_platform_failure(metrics):
                await self._persist_inconclusive_outcome(
                    trial.id,
                    metrics.get("observed_outcome") or {},
                    output,
                    metrics,
                )
                return

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
                        "case_type": getattr(case, "case_type", None) or "success",
                        "input": case.input_payload,
                        "initial_context": case.initial_context,
                        "expected_contract": case.expected_contract,
                        "expected_outcome": (case.expected_contract or {}).get("expected_outcome"),
                        "severity": case.severity,
                        "weight": case.weight,
                        "blocking": case.blocking,
                        "target_digest": {
                            "snapshot_hash": target.snapshot_hash,
                            "source_type": target.source_type,
                            "environment": target.environment,
                            "response_format": (target.snapshot or {}).get("response_format"),
                            "output_schema": (target.snapshot or {}).get("output_schema"),
                            "session_mode": (target.snapshot or {}).get("session_mode"),
                            "runtime_config": (target.snapshot or {}).get("runtime_config"),
                        },
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
            await self._persist_outcome_columns(trial.id, metrics.get("observed_outcome"))
        except EvaluationRuntimeCancelled as exc:
            await self._mark_trial_cancelled(trial.id, str(exc))
        except Exception as exc:
            observed = classify_runtime_failure(exc)
            await self._persist_inconclusive_outcome(
                trial.id,
                observed,
                {"answer": "", "observed_outcome": observed},
                {"runtime_completed": False, "observed_outcome": observed},
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
        await super()._persist_runtime_evidence(
            trial=trial,
            output=output,
            metrics=metrics,
            agent_run_id=agent_run_id,
            network_execution_id=network_execution_id,
            trace_id=trace_id,
        )
        await self._persist_outcome_columns(trial.id, metrics.get("observed_outcome"))

    async def _persist_outcome_columns(self, trial_id: UUID, observed: Any) -> None:
        if not isinstance(observed, dict):
            return
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial_id, with_for_update=True)
            if row is not None:
                row.observed_outcome = observed
                row.failure_origin = observed.get("failure_origin")
                row.failure_stage = observed.get("failure_stage")

    async def _persist_inconclusive_outcome(
        self,
        trial_id: UUID,
        observed: dict[str, Any],
        output: dict[str, Any],
        metrics: dict[str, Any],
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial_id, with_for_update=True)
            if row is None:
                return
            row.status = EvaluationTrialStatus.INCONCLUSIVE.value
            row.observed_outcome = observed
            row.failure_origin = observed.get("failure_origin")
            row.failure_stage = observed.get("failure_stage")
            row.failure_code = str(observed.get("failure_code") or "runtime_inconclusive")
            row.failure_detail = str(observed.get("failure_detail") or "")[:2000]
            row.output_payload = output
            row.metrics = {**metrics, "runtime_completed": True, "observed_outcome": observed}
            row.score = None
            row.passed = None
            row.completed_at = self._now()

    @staticmethod
    def _now():
        from modules.evaluation.application.processor import _utc_now

        return _utc_now()


class OutcomeAwareEvaluationRunWorker(ResumableEvaluationRunWorker):
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
        self._processor = OutcomeAwareEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = ["OutcomeAwareEvaluationRunProcessor", "OutcomeAwareEvaluationRunWorker"]
