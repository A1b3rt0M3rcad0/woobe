from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from modules.evaluation.application.evaluation_kpis import canonical_evaluation_kpis
from modules.evaluation.infra.database.evidence_revision_models import (
    EvaluationEvidenceRevisionModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationCheckResultModel,
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
)
from modules.evaluation.infra.judge import canonical_hash


def revision_number(run: EvaluationRunModel) -> int:
    aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
    try:
        return max(1, int(aggregate.get("evidence_revision") or 1))
    except (TypeError, ValueError):
        return 1


async def _turns_by_trial(session, trial_ids: list[UUID]) -> dict[str, list[dict[str, Any]]]:
    if not trial_ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT id, evaluation_trial_id, position, input_payload, output_payload, "
                "metrics, status, agent_session_id, network_session_id, agent_run_id, "
                "network_execution_id, trace_id, failure_code, failure_detail, "
                "started_at, completed_at "
                "FROM evaluation.trial_turns "
                "WHERE evaluation_trial_id = ANY(:trial_ids) "
                "ORDER BY evaluation_trial_id, position"
            ),
            {"trial_ids": trial_ids},
        )
    ).mappings().all()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["evaluation_trial_id"]), []).append(
            {
                "id": str(row["id"]),
                "position": int(row["position"]),
                "input_payload": row["input_payload"],
                "output": row["output_payload"],
                "metrics": row["metrics"],
                "status": row["status"],
                "agent_session_id": str(row["agent_session_id"])
                if row["agent_session_id"]
                else None,
                "network_session_id": str(row["network_session_id"])
                if row["network_session_id"]
                else None,
                "agent_run_id": str(row["agent_run_id"]) if row["agent_run_id"] else None,
                "network_execution_id": str(row["network_execution_id"])
                if row["network_execution_id"]
                else None,
                "trace_id": str(row["trace_id"]) if row["trace_id"] else None,
                "failure_code": row["failure_code"],
                "failure_detail": row["failure_detail"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat()
                if row["completed_at"]
                else None,
            }
        )
    return grouped


async def build_evidence_snapshot(session, run: EvaluationRunModel) -> dict[str, Any]:
    targets = list(
        (
            await session.scalars(
                select(EvaluationTargetModel).where(
                    EvaluationTargetModel.evaluation_run_id == run.id
                )
            )
        ).all()
    )
    trials = list(
        (
            await session.scalars(
                select(EvaluationTrialModel)
                .where(EvaluationTrialModel.evaluation_run_id == run.id)
                .order_by(EvaluationTrialModel.execution_order)
            )
        ).all()
    )
    case_ids = {trial.test_case_id for trial in trials}
    cases = {
        item.id: item
        for item in (
            await session.scalars(
                select(EvaluationTestCaseModel).where(
                    EvaluationTestCaseModel.id.in_(case_ids or {UUID(int=0)})
                )
            )
        ).all()
    }
    calls = list(
        (
            await session.scalars(
                select(EvaluatorModelCallModel).where(
                    EvaluatorModelCallModel.evaluation_run_id == run.id
                )
            )
        ).all()
    )
    checks = list(
        (
            await session.scalars(
                select(EvaluationCheckResultModel).where(
                    EvaluationCheckResultModel.evaluation_trial_id.in_(
                        [trial.id for trial in trials] or [UUID(int=0)]
                    )
                )
            )
        ).all()
    )
    checks_by_trial: dict[UUID, list[dict[str, Any]]] = {}
    for check in checks:
        checks_by_trial.setdefault(check.evaluation_trial_id, []).append(
            {
                "id": str(check.id),
                "evaluator_key": check.evaluator_key,
                "evaluator_type": check.evaluator_type,
                "dimension": check.dimension,
                "status": check.status,
                "score": check.score,
                "weight": check.weight,
                "blocking": check.blocking,
                "reason": check.reason,
                "evidence": check.evidence,
            }
        )
    turns = await _turns_by_trial(session, [trial.id for trial in trials])

    trial_payloads: list[dict[str, Any]] = []
    for trial in trials:
        case = cases.get(trial.test_case_id)
        input_payload = case.input_payload if case is not None else {}
        interaction_mode = (
            str(input_payload.get("interaction_mode") or "single_turn")
            if isinstance(input_payload, dict)
            else "single_turn"
        )
        trial_payloads.append(
            {
                "id": str(trial.id),
                "target_id": str(trial.evaluation_target_id),
                "test_case_id": str(trial.test_case_id),
                "repetition": trial.repetition,
                "pair_key": trial.pair_key,
                "status": trial.status,
                "score": trial.score,
                "passed": trial.passed,
                "agent_run_id": str(trial.agent_run_id) if trial.agent_run_id else None,
                "network_execution_id": str(trial.network_execution_id)
                if trial.network_execution_id
                else None,
                "trace_id": str(trial.root_trace_id) if trial.root_trace_id else None,
                "output": trial.output_payload,
                "metrics": trial.metrics,
                "observed_outcome": trial.observed_outcome,
                "failure_origin": trial.failure_origin,
                "failure_stage": trial.failure_stage,
                "failure_code": trial.failure_code,
                "failure_detail": trial.failure_detail,
                "interaction_mode": interaction_mode,
                "turns": turns.get(str(trial.id), []),
                "case": (
                    {
                        "id": str(case.id),
                        "name": case.name,
                        "case_type": case.case_type,
                        "interaction_mode": interaction_mode,
                        "position": case.position,
                        "input_payload": case.input_payload,
                        "turns": (
                            case.input_payload.get("turns", [])
                            if isinstance(case.input_payload, dict)
                            else []
                        ),
                        "initial_context": case.initial_context,
                        "expected_contract": case.expected_contract,
                        "severity": case.severity,
                        "weight": case.weight,
                        "blocking": case.blocking,
                        "production_frequency": case.production_frequency,
                    }
                    if case is not None
                    else None
                ),
                "checks": checks_by_trial.get(trial.id, []),
            }
        )

    aggregate = dict(run.aggregate_result) if isinstance(run.aggregate_result, dict) else {}
    kpis = canonical_evaluation_kpis(trial_payloads)
    aggregate["kpis"] = kpis
    run.aggregate_result = aggregate
    conclusive = sum(
        1 for trial in trials if trial.score is not None and trial.passed is not None
    )
    evidence_status = (
        "complete"
        if trials and conclusive == len(trials)
        else "partial"
        if conclusive
        else "unavailable"
    )
    return {
        "run": {
            "id": str(run.id),
            "project_id": str(run.project_id),
            "suite_version_id": str(run.suite_version_id),
            "mode": run.mode,
            "status": run.status,
            "repetitions": run.repetitions,
            "overall_score": run.overall_score,
            "pass_rate": run.pass_rate,
            "qualification_status": run.qualification_status,
            "measured_total_cost": float(run.measured_total_cost)
            if run.measured_total_cost is not None
            else None,
            "failure_code": run.failure_code,
            "failure_detail": run.failure_detail,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "aggregate_result": aggregate,
            "evidence_revision": revision_number(run),
        },
        "targets": [
            {
                "id": str(target.id),
                "side": target.side,
                "target_type": target.target_type,
                "source_type": target.source_type,
                "entity_id": str(target.entity_id),
                "environment": target.environment,
                "agent_release_id": str(target.agent_release_id)
                if target.agent_release_id
                else None,
                "network_version_id": str(target.network_version_id)
                if target.network_version_id
                else None,
                "snapshot": target.snapshot,
                "snapshot_hash": target.snapshot_hash,
                "composition_hash": target.composition_hash,
                "display_name": target.display_name,
                "display_version": target.display_version,
            }
            for target in targets
        ],
        "trials": trial_payloads,
        "judge_calls": [
            {
                "id": str(call.id),
                "trial_id": str(call.evaluation_trial_id),
                "provider_model_id": str(call.provider_model_id),
                "provider": call.provider,
                "model": call.model,
                "status": call.status,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "cost_usd": float(call.cost_usd) if call.cost_usd is not None else None,
                "cost_status": call.cost_status,
                "latency_ms": call.latency_ms,
                "structured_result": call.structured_result,
                "error": call.error,
                "pricing_snapshot": call.pricing_snapshot,
            }
            for call in calls
        ],
        "evidence_status": evidence_status,
        "evidence_completeness": {
            "total_trials": len(trials),
            "conclusive_trials": conclusive,
            "inconclusive_trials": max(0, len(trials) - conclusive),
        },
    }


async def capture_evidence_revision(
    session,
    run: EvaluationRunModel,
    *,
    reason: str,
    captured_by: UUID | None = None,
) -> EvaluationEvidenceRevisionModel:
    revision = revision_number(run)
    existing = await session.scalar(
        select(EvaluationEvidenceRevisionModel).where(
            EvaluationEvidenceRevisionModel.evaluation_run_id == run.id,
            EvaluationEvidenceRevisionModel.revision == revision,
        )
    )
    if existing is not None:
        return existing
    snapshot = await build_evidence_snapshot(session, run)
    assessment = (
        snapshot.get("run", {})
        .get("aggregate_result", {})
        .get("assessment")
    )
    row = EvaluationEvidenceRevisionModel(
        project_id=run.project_id,
        evaluation_run_id=run.id,
        revision=revision,
        assessment_hash=canonical_hash(assessment) if assessment else None,
        evidence_status=str(snapshot.get("evidence_status") or "unavailable"),
        snapshot=snapshot,
        captured_reason=reason,
        captured_by=captured_by,
    )
    session.add(row)
    await session.flush()
    return row


async def get_evidence_revision_snapshot(
    session,
    *,
    run_id: UUID,
    revision: int,
) -> dict[str, Any] | None:
    row = await session.scalar(
        select(EvaluationEvidenceRevisionModel).where(
            EvaluationEvidenceRevisionModel.evaluation_run_id == run_id,
            EvaluationEvidenceRevisionModel.revision == revision,
        )
    )
    return dict(row.snapshot) if row is not None else None


__all__ = [
    "build_evidence_snapshot",
    "capture_evidence_revision",
    "get_evidence_revision_snapshot",
    "revision_number",
]
