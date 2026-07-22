from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

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

    aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
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
        "trials": [
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
                "case": (
                    {
                        "id": str(cases[trial.test_case_id].id),
                        "name": cases[trial.test_case_id].name,
                        "case_type": cases[trial.test_case_id].case_type,
                        "position": cases[trial.test_case_id].position,
                        "input_payload": cases[trial.test_case_id].input_payload,
                        "initial_context": cases[trial.test_case_id].initial_context,
                        "expected_contract": cases[trial.test_case_id].expected_contract,
                        "severity": cases[trial.test_case_id].severity,
                        "weight": cases[trial.test_case_id].weight,
                        "blocking": cases[trial.test_case_id].blocking,
                        "production_frequency": cases[trial.test_case_id].production_frequency,
                    }
                    if trial.test_case_id in cases
                    else None
                ),
                "checks": checks_by_trial.get(trial.id, []),
            }
            for trial in trials
        ],
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
