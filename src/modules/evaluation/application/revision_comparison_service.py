from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any
from uuid import UUID

from modules.evaluation.application.evaluation_protocol import protocol_compatibility
from modules.evaluation.application.evidence_revision_snapshot import (
    capture_evidence_revision,
    get_evidence_revision_snapshot,
    revision_number,
)
from modules.evaluation.application.failure_taxonomy import summarize_failures
from modules.evaluation.application.immutable_catalog_service import (
    ImmutableEvaluationCatalogService,
)
from modules.evaluation.infra.database.catalog_models import EvaluationComparisonModel
from shared.infra.errors import NotFoundError

_ACTIVE = {
    "queued",
    "snapshotting",
    "executing",
    "judging",
    "aggregating",
    "cancel_requested",
}


def _run_data(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = snapshot.get("run")
    return dict(value) if isinstance(value, dict) else {}


def _targets(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in snapshot.get("targets") or [] if isinstance(item, dict)]


def _trials(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in snapshot.get("trials") or [] if isinstance(item, dict)]


def _calls(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in snapshot.get("judge_calls") or [] if isinstance(item, dict)]


def _single_target(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    values = _targets(snapshot)
    if len(values) == 1:
        return values[0]
    return next((item for item in values if item.get("side") == "single"), None)


def _summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    run = _run_data(snapshot)
    aggregate = run.get("aggregate_result")
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    target = _single_target(snapshot)
    summaries = aggregate.get("target_summaries")
    if isinstance(summaries, list):
        for item in summaries:
            if isinstance(item, dict) and str(item.get("target_id")) == str((target or {}).get("id")):
                return dict(item)
        if len(summaries) == 1 and isinstance(summaries[0], dict):
            return dict(summaries[0])
    return {
        "target_id": (target or {}).get("id"),
        "weighted_score": run.get("overall_score"),
        "weighted_pass_rate": run.get("pass_rate"),
    }


def _runtime(trials: list[dict[str, Any]]) -> dict[str, Any]:
    costs = [
        float(item["metrics"]["cost_usd"])
        for item in trials
        if isinstance(item.get("metrics"), dict)
        and item["metrics"].get("cost_usd") is not None
    ]
    latencies = [
        float(item["metrics"]["latency_ms"])
        for item in trials
        if isinstance(item.get("metrics"), dict)
        and item["metrics"].get("latency_ms") is not None
    ]
    return {
        "runtime_cost_usd": sum(costs) if costs else None,
        "latency_median_ms": median(latencies) if latencies else None,
        "pricing_coverage": len(costs) / len(trials) * 100 if trials else 0,
        "latency_sample_size": len(latencies),
    }


def _case_map(trials: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for trial in trials:
        case = trial.get("case")
        case = case if isinstance(case, dict) else {}
        case_id = str(case.get("id") or trial.get("test_case_id") or trial.get("pair_key"))
        result.setdefault(case_id, []).append(trial)
    return result


def _case_comparison(
    candidate_trials: list[dict[str, Any]],
    reference_trials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate = _case_map(candidate_trials)
    reference = _case_map(reference_trials)
    case_ids = set(candidate) | set(reference)

    def position(case_id: str) -> int:
        values = candidate.get(case_id) or reference.get(case_id) or []
        case = values[0].get("case") if values else {}
        return int(case.get("position") or 0) if isinstance(case, dict) else 0

    result: list[dict[str, Any]] = []
    for case_id in sorted(case_ids, key=position):
        c_values = candidate.get(case_id, [])
        r_values = reference.get(case_id, [])
        c_scores = [float(item["score"]) for item in c_values if item.get("score") is not None]
        r_scores = [float(item["score"]) for item in r_values if item.get("score") is not None]
        c_average = sum(c_scores) / len(c_scores) if c_scores else None
        r_average = sum(r_scores) / len(r_scores) if r_scores else None
        score_delta = (
            c_average - r_average
            if c_average is not None and r_average is not None
            else None
        )
        winner = (
            "tie"
            if score_delta is not None and abs(score_delta) < 0.001
            else "candidate"
            if score_delta is not None and score_delta > 0
            else "reference"
            if score_delta is not None
            else None
        )
        values = c_values or r_values
        case = values[0].get("case") if values else {}
        case = case if isinstance(case, dict) else {}
        result.append(
            {
                "test_case_id": case_id,
                "name": case.get("name") or case_id,
                "case_type": case.get("case_type"),
                "candidate": {
                    "score": c_average,
                    "passed": sum(1 for item in c_values if item.get("passed") is True),
                    "total": len(c_values),
                    "conclusive": len(c_scores),
                },
                "reference": {
                    "score": r_average,
                    "passed": sum(1 for item in r_values if item.get("passed") is True),
                    "total": len(r_values),
                    "conclusive": len(r_scores),
                },
                "score_delta": score_delta,
                "winner": winner,
            }
        )
    return result


def _failure_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    return summarize_failures(_trials(snapshot), _calls(snapshot))


def _run_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    run = _run_data(snapshot)
    aggregate = run.get("aggregate_result")
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    assessment = aggregate.get("assessment")
    assessment = assessment if isinstance(assessment, dict) else {}
    return {
        "id": run.get("id"),
        "suite_version_id": run.get("suite_version_id"),
        "status": run.get("status"),
        "mode": run.get("mode"),
        "repetitions": run.get("repetitions"),
        "evidence_revision": run.get("evidence_revision", 1),
        "assessment_status": assessment.get("status") or "inconclusive",
        "overall_score": run.get("overall_score"),
        "pass_rate": run.get("pass_rate"),
        "measured_total_cost": run.get("measured_total_cost"),
        "failure_code": run.get("failure_code"),
        "failure_detail": run.get("failure_detail"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "created_at": run.get("created_at"),
    }


def _target_payload(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    target = _single_target(snapshot)
    if target is None:
        return None
    return {
        key: target.get(key)
        for key in (
            "id",
            "target_type",
            "source_type",
            "entity_id",
            "environment",
            "snapshot_hash",
            "display_name",
            "display_version",
            "agent_release_id",
            "network_version_id",
        )
    }


def _public_run(snapshot: dict[str, Any], failures: dict[str, Any]) -> dict[str, Any]:
    run = _run_data(snapshot)
    return {
        **run,
        "targets": _targets(snapshot),
        "trials": _trials(snapshot),
        "judge_calls": _calls(snapshot),
        "evidence_status": snapshot.get("evidence_status"),
        "evidence_completeness": snapshot.get("evidence_completeness"),
        "failure_summary": failures,
    }


class RevisionComparisonCatalogService(ImmutableEvaluationCatalogService):
    """Calculate and render Comparisons from immutable revision snapshots."""

    async def _snapshot_for(self, session, run, revision: int) -> dict[str, Any] | None:
        snapshot = await get_evidence_revision_snapshot(
            session,
            run_id=run.id,
            revision=revision,
        )
        if snapshot is not None:
            return snapshot
        if revision != revision_number(run) or run.status in _ACTIVE:
            return None
        row = await capture_evidence_revision(
            session,
            run,
            reason="comparison_materialized",
        )
        return dict(row.snapshot)

    async def _refresh_comparison(
        self,
        session,
        comparison: EvaluationComparisonModel,
    ) -> None:
        if comparison.completed_at is not None and isinstance(
            comparison.aggregate_result,
            dict,
        ):
            return
        candidate_run = await self._load_run(
            session,
            comparison.project_id,
            comparison.candidate_run_id,
        )
        reference_run = await self._load_run(
            session,
            comparison.project_id,
            comparison.reference_run_id,
        )
        if candidate_run.status in _ACTIVE or reference_run.status in _ACTIVE:
            comparison.status = "running"
            comparison.aggregate_result = {
                "comparison_available": False,
                "reason": "evaluation_runs_in_progress",
                "candidate": {"run": self._run_summary(candidate_run)},
                "reference": {"run": self._run_summary(reference_run)},
            }
            return

        candidate_hash = await self._protocol_for_run(session, candidate_run)
        reference_hash = await self._protocol_for_run(session, reference_run)
        compatibility = protocol_compatibility(
            candidate_hash,
            reference_hash,
            candidate_repetitions=candidate_run.repetitions,
            reference_repetitions=reference_run.repetitions,
        )
        if not compatibility["compatible"]:
            comparison.status = "incompatible"
            comparison.failure_code = str(compatibility["reason"])
            comparison.failure_detail = " ".join(compatibility["warnings"])
            comparison.aggregate_result = {"compatibility": compatibility}
            comparison.completed_at = datetime.now(timezone.utc)
            return

        candidate = await self._snapshot_for(
            session,
            candidate_run,
            comparison.candidate_evidence_revision,
        )
        reference = await self._snapshot_for(
            session,
            reference_run,
            comparison.reference_evidence_revision,
        )
        if candidate is None or reference is None:
            comparison.status = "blocked"
            comparison.failure_code = "evidence_revision_snapshot_missing"
            comparison.failure_detail = (
                "The selected historical evidence revision was not captured. "
                "Select a persisted revision or run the Evaluation again."
            )
            comparison.aggregate_result = {
                "comparison_available": False,
                "reason": comparison.failure_code,
            }
            comparison.completed_at = datetime.now(timezone.utc)
            return

        c_summary = _summary(candidate)
        r_summary = _summary(reference)
        c_trials = _trials(candidate)
        r_trials = _trials(reference)
        c_runtime = _runtime(c_trials)
        r_runtime = _runtime(r_trials)
        c_failures = _failure_summary(candidate)
        r_failures = _failure_summary(reference)
        cases = _case_comparison(c_trials, r_trials)
        c_score = c_summary.get("weighted_score")
        r_score = r_summary.get("weighted_score")
        c_pass = c_summary.get("weighted_pass_rate")
        r_pass = r_summary.get("weighted_pass_rate")
        wins = sum(1 for item in cases if item.get("winner") == "candidate")
        losses = sum(1 for item in cases if item.get("winner") == "reference")
        ties = sum(1 for item in cases if item.get("winner") == "tie")
        if c_score is None and r_score is None:
            status = "blocked"
            reason = "no_scored_judge_evidence"
        elif c_score is None or r_score is None:
            status = "partial"
            reason = "one_evaluation_is_inconclusive"
        else:
            status = "ready"
            reason = None

        comparison.status = status
        comparison.failure_code = reason
        comparison.failure_detail = (
            "The target outputs are preserved, but one or both Evaluation revisions lack scored Judge evidence."
            if reason
            else None
        )
        comparison.completed_at = datetime.now(timezone.utc)
        comparison.aggregate_result = {
            "comparison_available": status == "ready",
            "comparison_kind": (
                "paired"
                if comparison.comparison_mode == "paired"
                else compatibility["comparison_kind"]
            ),
            "compatibility": compatibility,
            "candidate": {
                "run": _run_summary(candidate),
                "target": _target_payload(candidate),
                "summary": c_summary,
                "runtime": c_runtime,
                "failures": c_failures,
            },
            "reference": {
                "run": _run_summary(reference),
                "target": _target_payload(reference),
                "summary": r_summary,
                "runtime": r_runtime,
                "failures": r_failures,
            },
            "delta": {
                "score": float(c_score) - float(r_score)
                if c_score is not None and r_score is not None
                else None,
                "pass_rate_percentage_points": float(c_pass) - float(r_pass)
                if c_pass is not None and r_pass is not None
                else None,
                "runtime_cost_usd": (
                    float(c_runtime["runtime_cost_usd"])
                    - float(r_runtime["runtime_cost_usd"])
                    if c_runtime["runtime_cost_usd"] is not None
                    and r_runtime["runtime_cost_usd"] is not None
                    else None
                ),
                "latency_median_ms": (
                    float(c_runtime["latency_median_ms"])
                    - float(r_runtime["latency_median_ms"])
                    if c_runtime["latency_median_ms"] is not None
                    and r_runtime["latency_median_ms"] is not None
                    else None
                ),
            },
            "case_outcomes": {
                "candidate_wins": wins,
                "reference_wins": losses,
                "ties": ties,
                "unavailable": len(cases) - wins - losses - ties,
            },
            "cases": cases,
            "reason": reason,
        }

    async def get_comparison(
        self,
        *,
        project_id: UUID,
        comparison_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(
                EvaluationComparisonModel,
                comparison_id,
                with_for_update=True,
            )
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Comparison not found")
            await self._refresh_comparison(session, row)
            candidate_run = await self._load_run(session, project_id, row.candidate_run_id)
            reference_run = await self._load_run(session, project_id, row.reference_run_id)
            candidate = await self._snapshot_for(
                session,
                candidate_run,
                row.candidate_evidence_revision,
            )
            reference = await self._snapshot_for(
                session,
                reference_run,
                row.reference_evidence_revision,
            )
            payload = await self._comparison_payload(session, row)
            payload["candidate_run"] = (
                _public_run(candidate, _failure_summary(candidate))
                if candidate is not None
                else None
            )
            payload["reference_run"] = (
                _public_run(reference, _failure_summary(reference))
                if reference is not None
                else None
            )
            return payload


__all__ = ["RevisionComparisonCatalogService"]
