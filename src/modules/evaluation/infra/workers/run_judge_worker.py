from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.run_judge import (
    selected_judge_config,
    selected_judge_provider_model_id,
)
from modules.evaluation.application.runtime_gateway import EvaluationRuntimeCancelled
from modules.evaluation.application.scoring import (
    DeterministicCheck,
    calculate_trial_score,
    evaluate_deterministic_checks,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.runtime_safe_judge import RuntimeSafeEvaluatorModelGateway
from modules.evaluation.infra.workers.integrity_worker import (
    IntegrityEvaluationRunProcessor,
    IntegrityEvaluationRunWorker,
)
from modules.observability.infra.database.models import TraceModel
from shared.infra.config import Settings


def effective_suite_for_run(run: Any, suite: Any) -> Any:
    """Project the immutable Suite rules with the Judge frozen on this Run."""

    return SimpleNamespace(
        judge_provider_model_id=selected_judge_provider_model_id(
            run,
            suite.judge_provider_model_id,
        ),
        judge_config=selected_judge_config(run, suite.judge_config),
        rubric=suite.rubric,
        deterministic_checks=suite.deterministic_checks,
    )


def _interaction_mode(case: Any) -> str:
    payload = case.input_payload if isinstance(case.input_payload, dict) else {}
    return str(payload.get("interaction_mode") or "single_turn")


def _session_turns(case: Any) -> list[dict[str, Any]]:
    payload = case.input_payload if isinstance(case.input_payload, dict) else {}
    turns = payload.get("turns")
    return [dict(item) for item in turns if isinstance(item, dict)] if isinstance(turns, list) else []


def _sum_optional(values: list[Any]) -> float | None:
    normalized: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            normalized.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(normalized) if normalized else None


def _sum_optional_int(values: list[Any]) -> int | None:
    value = _sum_optional(values)
    return int(value) if value is not None else None


def _turn_checks(
    turn: dict[str, Any],
    *,
    position: int,
    output: dict[str, Any],
    metrics: dict[str, Any],
) -> list[DeterministicCheck]:
    contract = turn.get("expected_contract")
    if not isinstance(contract, dict) or not contract:
        return []
    return [
        replace(
            item,
            key=f"turn:{position}:{item.key}",
            evidence={**item.evidence, "turn_position": position},
        )
        for item in evaluate_deterministic_checks(
            contract,
            output=output,
            metrics=metrics,
            suite_checks={},
        )
    ]


def _serialized_checks(values: list[DeterministicCheck]) -> list[dict[str, Any]]:
    return [
        {
            "key": item.key,
            "dimension": item.dimension,
            "status": item.status,
            "score": item.score,
            "blocking": item.blocking,
            "reason": item.reason,
            "evidence": item.evidence,
            "weight": item.weight,
        }
        for item in values
    ]


class RunJudgeEvaluationRunProcessor(IntegrityEvaluationRunProcessor):
    """Execute the frozen Judge protocol and stateful multi-turn Session Tests."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(session_factory, settings=settings)
        self._judge = RuntimeSafeEvaluatorModelGateway(settings)

    async def _execute_trial(self, trial, target, case, suite) -> None:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, trial.evaluation_run_id)
        effective_suite = effective_suite_for_run(run, suite) if run is not None else suite
        if _interaction_mode(case) != "session":
            return await super()._execute_trial(trial, target, case, effective_suite)
        try:
            await self._execute_session_trial(trial, target, case, effective_suite)
        finally:
            self._release_canary(trial.id)

    async def _execute_session_trial(self, trial, target, case, suite) -> None:
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
                if target.target_type == "agent":
                    (
                        output,
                        metrics,
                        agent_run_id,
                        trace_id,
                    ) = await self._execute_agent_session(trial, target, case)
                    network_execution_id = None
                else:
                    (
                        output,
                        metrics,
                        network_execution_id,
                        trace_id,
                    ) = await self._execute_network_session(trial, target, case)
                    agent_run_id = None
                await self._persist_runtime_evidence(
                    trial=trial,
                    output=output,
                    metrics=metrics,
                    agent_run_id=agent_run_id,
                    network_execution_id=network_execution_id,
                    trace_id=trace_id,
                )

            deterministic = evaluate_deterministic_checks(
                case.expected_contract,
                output=output,
                metrics=metrics,
                suite_checks=suite.deterministic_checks or {},
            )
            transcript = (
                output.get("transcript")
                if isinstance(output.get("transcript"), list)
                else []
            )
            for position, turn in enumerate(_session_turns(case), start=1):
                observed = (
                    transcript[position - 1]
                    if position <= len(transcript)
                    and isinstance(transcript[position - 1], dict)
                    else {}
                )
                turn_output = (
                    observed.get("output")
                    if isinstance(observed.get("output"), dict)
                    else {}
                )
                turn_metrics = (
                    observed.get("metrics")
                    if isinstance(observed.get("metrics"), dict)
                    else {}
                )
                deterministic.extend(
                    _turn_checks(
                        turn,
                        position=position,
                        output=turn_output,
                        metrics=turn_metrics,
                    )
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
                        "interaction_mode": "session",
                        "turns": _session_turns(case),
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
            return
        except Exception as exc:
            # Once the transcript is complete, a Judge failure must remain
            # judgment-retryable without replaying the Agent/Network Session.
            async with self._session_factory() as session:
                persisted = await session.get(EvaluationTrialModel, trial.id)
                persisted_output = (
                    dict(persisted.output_payload)
                    if persisted is not None
                    and isinstance(persisted.output_payload, dict)
                    else None
                )
                persisted_metrics = (
                    dict(persisted.metrics)
                    if persisted is not None and isinstance(persisted.metrics, dict)
                    else {}
                )
            if persisted_output is not None and persisted_metrics.get(
                "runtime_completed"
            ):
                observed = {
                    "type": "failure",
                    "failure_origin": "platform",
                    "failure_stage": "judge",
                    "failure_code": "judge_failed",
                    "failure_detail": str(exc)[:2000],
                }
                await self._persist_inconclusive_outcome(
                    trial.id,
                    observed,
                    persisted_output,
                    persisted_metrics,
                )
                return

            # A target/runtime failure belongs to this Session Trial only. Completed
            # turn rows remain immutable evidence and the worker continues the Run.
            (
                partial_output,
                partial_metrics,
                agent_run_id,
                network_execution_id,
                trace_id,
            ) = await self._partial_session_evidence(trial, target, case)
            async with self._session_factory() as session, session.begin():
                row = await session.get(
                    EvaluationTrialModel,
                    trial.id,
                    with_for_update=True,
                )
                if row is not None and row.completed_at is None:
                    row.status = "failed"
                    row.output_payload = partial_output
                    row.metrics = {
                        **partial_metrics,
                        "runtime_completed": False,
                    }
                    row.agent_run_id = agent_run_id
                    row.network_execution_id = network_execution_id
                    row.root_trace_id = trace_id
                    row.failure_code = type(exc).__name__
                    row.failure_detail = str(exc)[:4000]
                    row.runtime_completed_at = datetime.now(timezone.utc)
                    row.completed_at = datetime.now(timezone.utc)
            return

    async def _execute_agent_session(self, trial, target, case):
        turns = _session_turns(case)
        if len(turns) < 2:
            raise ValueError("Session Test requires at least two turns")
        agent_session_id: UUID | None = None
        transcript: list[dict[str, Any]] = []
        metrics_by_turn: list[dict[str, Any]] = []
        last_agent_run_id: UUID | None = None
        last_trace_id: UUID | None = None

        for position, turn in enumerate(turns, start=1):
            await self._ensure_not_cancelled(trial.evaluation_run_id)
            message = str((turn.get("input_payload") or {}).get("message") or "").strip()
            started_at = datetime.now(timezone.utc)
            try:
                result = await self._agent_invoker.invoke(
                    project_id=trial.project_id,
                    agent_id=target.entity_id,
                    release_id=target.agent_release_id,
                    snapshot_override=target.snapshot if target.source_type == "draft" else None,
                    message=message,
                    agent_session_id=agent_session_id,
                    execution_context="playground",
                    internal_tools=[],
                    network_context={
                        "run_purpose": "evaluation",
                        "evaluation_run_id": str(trial.evaluation_run_id),
                        "evaluation_trial_id": str(trial.id),
                        "evaluation_target_id": str(target.id),
                        "target_snapshot_hash": target.snapshot_hash,
                        "target_snapshot_label": target.environment,
                        "evaluation_role": "target",
                        "comparison_pair_id": trial.pair_key,
                        "target_side": target.side,
                        "evaluation_turn_position": position,
                        "initial_context": case.initial_context,
                    },
                )
                agent_session_id = result.session_id or agent_session_id
                result_agent_run_id = (
                    getattr(result, "agent_run_id", None)
                    or getattr(result, "run_id", None)
                )
                last_agent_run_id = result_agent_run_id or last_agent_run_id
                last_trace_id = result.trace_id or last_trace_id
                usage = result.usage or {}
                trace = None
                if result.trace_id is not None:
                    async with self._session_factory() as session:
                        trace = await session.get(TraceModel, result.trace_id)
                elapsed_ms = round(
                    (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
                )
                output = {
                    "answer": result.answer,
                    "parsed_output": result.parsed_output,
                    "output_parse_error": result.output_parse_error,
                    "tool_calls": result.tool_calls or [],
                    "sources": result.sources or [],
                }
                turn_metrics = {
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
                    "agent_run_count": 1,
                    "provider": result.provider,
                    "model": result.model,
                }
                deterministic = _turn_checks(
                    turn,
                    position=position,
                    output=output,
                    metrics=turn_metrics,
                )
                if deterministic:
                    turn_metrics["deterministic_checks"] = _serialized_checks(
                        deterministic
                    )
                transcript.append(
                    {
                        "position": position,
                        "input": {"message": message},
                        "output": output,
                        "expected_behavior": turn.get("expected_behavior") or [],
                        "forbidden_behavior": turn.get("forbidden_behavior") or [],
                        "metrics": turn_metrics,
                    }
                )
                metrics_by_turn.append(turn_metrics)
                await self._persist_turn(
                    trial_id=trial.id,
                    project_id=trial.project_id,
                    position=position,
                    input_payload={"message": message},
                    output=output,
                    metrics=turn_metrics,
                    status="completed",
                    agent_session_id=agent_session_id,
                    agent_run_id=result_agent_run_id,
                    trace_id=result.trace_id,
                    started_at=started_at,
                )
            except Exception as exc:
                await self._persist_turn(
                    trial_id=trial.id,
                    project_id=trial.project_id,
                    position=position,
                    input_payload={"message": message},
                    output=None,
                    metrics=None,
                    status="failed",
                    agent_session_id=agent_session_id,
                    failure_code=type(exc).__name__,
                    failure_detail=str(exc),
                    started_at=started_at,
                )
                raise

        return self._session_result(
            transcript,
            metrics_by_turn,
            session_id=agent_session_id,
            target_type="agent",
            planned_turn_count=len(turns),
            session_completed=True,
        ) + (last_agent_run_id, last_trace_id)

    async def _execute_network_session(self, trial, target, case):
        turns = _session_turns(case)
        if len(turns) < 2:
            raise ValueError("Session Test requires at least two turns")
        network_session_id: UUID | None = None
        transcript: list[dict[str, Any]] = []
        metrics_by_turn: list[dict[str, Any]] = []
        last_execution_id: UUID | None = None
        last_trace_id: UUID | None = None

        for position, turn in enumerate(turns, start=1):
            await self._ensure_not_cancelled(trial.evaluation_run_id)
            message = str((turn.get("input_payload") or {}).get("message") or "").strip()
            started_at = datetime.now(timezone.utc)
            try:
                evidence = await self._network_gateway.execute(
                    evaluation_run_id=trial.evaluation_run_id,
                    evaluation_trial_id=trial.id,
                    pair_key=trial.pair_key,
                    target_side=target.side,
                    project_id=trial.project_id,
                    target=target,
                    message=message,
                    initial_context=case.initial_context,
                    network_session_id=network_session_id,
                    turn_position=position,
                )
                network_session_id = evidence.network_session_id
                last_execution_id = evidence.network_execution_id
                last_trace_id = evidence.root_trace_id or last_trace_id
                transcript.append(
                    {
                        "position": position,
                        "input": {"message": message},
                        "output": evidence.output,
                        "expected_behavior": turn.get("expected_behavior") or [],
                        "forbidden_behavior": turn.get("forbidden_behavior") or [],
                        "metrics": evidence.metrics,
                    }
                )
                deterministic = _turn_checks(
                    turn,
                    position=position,
                    output=evidence.output,
                    metrics=evidence.metrics,
                )
                if deterministic:
                    evidence.metrics["deterministic_checks"] = _serialized_checks(
                        deterministic
                    )
                metrics_by_turn.append(evidence.metrics)
                await self._persist_turn(
                    trial_id=trial.id,
                    project_id=trial.project_id,
                    position=position,
                    input_payload={"message": message},
                    output=evidence.output,
                    metrics=evidence.metrics,
                    status="completed",
                    network_session_id=network_session_id,
                    network_execution_id=evidence.network_execution_id,
                    trace_id=evidence.root_trace_id,
                    started_at=started_at,
                )
            except Exception as exc:
                await self._persist_turn(
                    trial_id=trial.id,
                    project_id=trial.project_id,
                    position=position,
                    input_payload={"message": message},
                    output=None,
                    metrics=None,
                    status="failed",
                    network_session_id=network_session_id,
                    failure_code=type(exc).__name__,
                    failure_detail=str(exc),
                    started_at=started_at,
                )
                raise

        output, metrics = self._session_result(
            transcript,
            metrics_by_turn,
            session_id=network_session_id,
            target_type="network",
            planned_turn_count=len(turns),
            session_completed=True,
        )
        return output, metrics, last_execution_id, last_trace_id

    @staticmethod
    def _session_result(
        transcript: list[dict[str, Any]],
        metrics_by_turn: list[dict[str, Any]],
        *,
        session_id: UUID | None,
        target_type: str,
        planned_turn_count: int,
        session_completed: bool,
        failure_turn: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        last_output = next(
            (
                item["output"]
                for item in reversed(transcript)
                if isinstance(item.get("output"), dict)
            ),
            {},
        )
        all_tools = [
            tool
            for item in transcript
            for tool in (item.get("output") or {}).get("tool_calls", [])
        ]
        all_sources = [
            source
            for item in transcript
            for source in (item.get("output") or {}).get("sources", [])
        ]
        output = {
            "answer": last_output.get("answer", ""),
            "parsed_output": last_output.get("parsed_output"),
            "output_parse_error": last_output.get("output_parse_error"),
            "tool_calls": all_tools,
            "sources": all_sources,
            "transcript": transcript,
        }
        costs = [item.get("cost_usd") for item in metrics_by_turn]
        latencies = [item.get("latency_ms") for item in metrics_by_turn]
        input_tokens = [item.get("input_tokens") for item in metrics_by_turn]
        output_tokens = [item.get("output_tokens") for item in metrics_by_turn]
        metrics = {
            "interaction_mode": "session",
            "session_completed": session_completed,
            "session_status": "completed" if session_completed else "failed",
            "turn_count": planned_turn_count,
            "attempted_turn_count": len(transcript),
            "completed_turn_count": len(metrics_by_turn),
            "failure_turn": failure_turn,
            "latency_ms": _sum_optional(latencies),
            "cost_usd": _sum_optional(costs),
            "input_tokens": _sum_optional_int(input_tokens),
            "output_tokens": _sum_optional_int(output_tokens),
            "tool_call_count": sum(
                int(item.get("tool_call_count") or 0) for item in metrics_by_turn
            ),
            "source_count": sum(
                int(item.get("source_count") or 0) for item in metrics_by_turn
            ),
            "agent_run_count": sum(
                int(item.get("agent_run_count") or 0) for item in metrics_by_turn
            ),
            "run_purpose": "evaluation",
            "session_id": str(session_id) if session_id else None,
            "session_target_type": target_type,
        }
        return output, metrics

    async def _partial_session_evidence(
        self,
        trial,
        target,
        case,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        UUID | None,
        UUID | None,
        UUID | None,
    ]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT position, input_payload, output_payload, metrics, status, "
                        "agent_session_id, network_session_id, agent_run_id, "
                        "network_execution_id, trace_id, failure_code, failure_detail "
                        "FROM evaluation.trial_turns "
                        "WHERE evaluation_trial_id = :trial_id "
                        "ORDER BY position"
                    ),
                    {"trial_id": trial.id},
                )
            ).mappings().all()
        defined_turns = _session_turns(case)
        transcript: list[dict[str, Any]] = []
        completed_metrics: list[dict[str, Any]] = []
        failure_turn: int | None = None
        agent_run_id: UUID | None = None
        network_execution_id: UUID | None = None
        trace_id: UUID | None = None
        session_id: UUID | None = None
        for row in rows:
            position = int(row["position"])
            definition = (
                defined_turns[position - 1]
                if position <= len(defined_turns)
                else {}
            )
            metrics = row["metrics"] if isinstance(row["metrics"], dict) else {}
            transcript.append(
                {
                    "position": position,
                    "input": row["input_payload"],
                    "output": row["output_payload"],
                    "expected_behavior": definition.get("expected_behavior") or [],
                    "forbidden_behavior": definition.get("forbidden_behavior") or [],
                    "metrics": metrics,
                    "status": row["status"],
                    "failure_code": row["failure_code"],
                    "failure_detail": row["failure_detail"],
                }
            )
            if row["status"] == "completed":
                completed_metrics.append(metrics)
            elif failure_turn is None:
                failure_turn = position
            agent_run_id = row["agent_run_id"] or agent_run_id
            network_execution_id = (
                row["network_execution_id"] or network_execution_id
            )
            trace_id = row["trace_id"] or trace_id
            session_id = (
                row["agent_session_id"]
                or row["network_session_id"]
                or session_id
            )
        output, metrics = self._session_result(
            transcript,
            completed_metrics,
            session_id=session_id,
            target_type=target.target_type,
            planned_turn_count=len(defined_turns),
            session_completed=False,
            failure_turn=failure_turn,
        )
        return output, metrics, agent_run_id, network_execution_id, trace_id

    async def _persist_turn(
        self,
        *,
        trial_id: UUID,
        project_id: UUID,
        position: int,
        input_payload: dict[str, Any],
        output: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        status: str,
        agent_session_id: UUID | None = None,
        network_session_id: UUID | None = None,
        agent_run_id: UUID | None = None,
        network_execution_id: UUID | None = None,
        trace_id: UUID | None = None,
        failure_code: str | None = None,
        failure_detail: str | None = None,
        started_at: datetime | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO evaluation.trial_turns ("
                    "id, project_id, evaluation_trial_id, position, input_payload, "
                    "output_payload, metrics, status, agent_session_id, network_session_id, "
                    "agent_run_id, network_execution_id, trace_id, failure_code, failure_detail, "
                    "started_at, completed_at, created_at, updated_at) VALUES ("
                    ":id, :project_id, :trial_id, :position, CAST(:input_payload AS jsonb), "
                    "CAST(:output_payload AS jsonb), CAST(:metrics AS jsonb), :status, "
                    ":agent_session_id, :network_session_id, :agent_run_id, :network_execution_id, "
                    ":trace_id, :failure_code, :failure_detail, :started_at, :completed_at, :created_at, :updated_at) "
                    "ON CONFLICT (evaluation_trial_id, position) DO UPDATE SET "
                    "output_payload = EXCLUDED.output_payload, metrics = EXCLUDED.metrics, "
                    "status = EXCLUDED.status, agent_session_id = EXCLUDED.agent_session_id, "
                    "network_session_id = EXCLUDED.network_session_id, "
                    "agent_run_id = EXCLUDED.agent_run_id, network_execution_id = EXCLUDED.network_execution_id, "
                    "trace_id = EXCLUDED.trace_id, failure_code = EXCLUDED.failure_code, "
                    "failure_detail = EXCLUDED.failure_detail, completed_at = EXCLUDED.completed_at, "
                    "updated_at = EXCLUDED.updated_at"
                ),
                {
                    "id": uuid4(),
                    "project_id": project_id,
                    "trial_id": trial_id,
                    "position": position,
                    "input_payload": self._json(input_payload),
                    "output_payload": self._json(output),
                    "metrics": self._json(metrics),
                    "status": status,
                    "agent_session_id": agent_session_id,
                    "network_session_id": network_session_id,
                    "agent_run_id": agent_run_id,
                    "network_execution_id": network_execution_id,
                    "trace_id": trace_id,
                    "failure_code": failure_code,
                    "failure_detail": str(failure_detail or "")[:4000] or None,
                    "started_at": started_at or now,
                    "completed_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    @staticmethod
    def _json(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False, default=str)

    async def _persist_final_result(self, **kwargs: Any) -> None:
        await super()._persist_final_result(**kwargs)
        trial = kwargs["trial"]
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationTrialModel, trial.id, with_for_update=True)
            if row is None:
                return
            metrics = dict(row.metrics or {})
            metrics["evaluation_worker"] = {
                "processor": "RunJudgeEvaluationRunProcessor",
                "processor_version": "run-judge-evaluation-worker-v3",
                "judge_gateway": "RuntimeSafeEvaluatorModelGateway",
                "expected_runtime_safe_gateway": "runtime-safe-judge-v2",
                "expected_governed_gateway": "governed-judge-v1",
                "expected_adaptive_gateway": "adaptive-judge-v4",
                "context_budgeting": "budgeted-evaluator-gateway",
                "run_level_judge_selection": True,
                "session_test_support": True,
            }
            judge = kwargs.get("judge")
            structured = getattr(judge, "structured_result", None)
            dimensions = (
                structured.get("dimensions")
                if isinstance(structured, dict)
                and isinstance(structured.get("dimensions"), dict)
                else {}
            )
            if dimensions:
                metrics["session_dimensions"] = dimensions
            row.metrics = metrics


class RunJudgeEvaluationRunWorker(IntegrityEvaluationRunWorker):
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
        self._processor = RunJudgeEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = [
    "RunJudgeEvaluationRunProcessor",
    "RunJudgeEvaluationRunWorker",
    "effective_suite_for_run",
]
