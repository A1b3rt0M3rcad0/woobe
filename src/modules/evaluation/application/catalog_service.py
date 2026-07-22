from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from modules.evaluation.application.evaluation_protocol import (
    evaluation_protocol_hash,
    protocol_compatibility,
    target_identity_hash,
)
from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.application.failure_taxonomy import summarize_failures
from modules.evaluation.infra.database.catalog_models import (
    EvaluationComparisonDecisionModel,
    EvaluationComparisonModel,
    EvaluationModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError

_ACTIVE_RUN_STATUSES = {
    "queued",
    "snapshotting",
    "executing",
    "judging",
    "aggregating",
    "cancel_requested",
}
_TERMINAL_RUN_STATUSES = {
    "completed",
    "partially_completed",
    "failed",
    "cancelled",
}


def _revision(run: EvaluationRunModel) -> int:
    aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
    try:
        return max(1, int(aggregate.get("evidence_revision") or 1))
    except (TypeError, ValueError):
        return 1


def _target_version_id(target: EvaluationTargetModel) -> UUID | None:
    return target.agent_release_id or target.network_version_id


def _summary_for(run: EvaluationRunModel, target_id: UUID | None) -> dict[str, Any]:
    aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
    summaries = aggregate.get("target_summaries")
    if isinstance(summaries, list):
        for item in summaries:
            if isinstance(item, dict) and str(item.get("target_id")) == str(target_id):
                return dict(item)
        if len(summaries) == 1 and isinstance(summaries[0], dict):
            return dict(summaries[0])
    assessment = aggregate.get("assessment")
    assessment = assessment if isinstance(assessment, dict) else {}
    return {
        "target_id": str(target_id) if target_id else None,
        "weighted_score": run.overall_score,
        "weighted_pass_rate": run.pass_rate,
        "completed_trial_count": assessment.get("completed_trial_count", 0),
    }


def _assessment(run: EvaluationRunModel) -> str:
    aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
    value = aggregate.get("assessment")
    if isinstance(value, dict) and isinstance(value.get("status"), str):
        return str(value["status"])
    if run.status in _ACTIVE_RUN_STATUSES:
        return "pending"
    return "inconclusive"


def _target_runtime_metrics(trials: list[EvaluationTrialModel]) -> dict[str, Any]:
    costs = [
        float((trial.metrics or {}).get("cost_usd"))
        for trial in trials
        if (trial.metrics or {}).get("cost_usd") is not None
    ]
    latencies = [
        float((trial.metrics or {}).get("latency_ms"))
        for trial in trials
        if (trial.metrics or {}).get("latency_ms") is not None
    ]
    return {
        "runtime_cost_usd": sum(costs) if costs else None,
        "latency_median_ms": median(latencies) if latencies else None,
        "pricing_coverage": len(costs) / len(trials) * 100 if trials else 0,
        "latency_sample_size": len(latencies),
    }


class EvaluationCatalogService:
    """Durable Evaluation identity plus reusable, evidence-based Comparisons."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._runs = EvaluationExperienceService(session_factory)

    async def preview_evaluation(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        target: dict[str, Any],
        acknowledge_tool_side_effects: bool = False,
        approved_high_risk_tool_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        payload = await self._runs.preview_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=target,
            baseline=None,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids or [],
        )
        async with self._session_factory() as session:
            suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            protocol_hash = evaluation_protocol_hash(suite)
        return {
            **payload,
            "mode": "single_snapshot",
            "target": payload.get("candidate"),
            "candidate": None,
            "baseline": None,
            "evaluation_protocol_hash": protocol_hash,
            "operations": {
                "evaluation_runs": 1,
                "comparisons": 0,
            },
        }

    async def create_evaluation_run(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        target: dict[str, Any],
        requested_by: UUID | None,
        acknowledge_tool_side_effects: bool = False,
        approved_high_risk_tool_ids: list[UUID] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        run_payload = await self._runs.create_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=target,
            baseline=None,
            requested_by=requested_by,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids or [],
            idempotency_key=idempotency_key,
        )
        evaluation = await self.attach_run_to_evaluation(
            project_id=project_id,
            run_id=UUID(str(run_payload["id"])),
            created_by=requested_by,
        )
        return {
            **run_payload,
            "evaluation_id": evaluation["id"],
            "evaluation_protocol_hash": evaluation["evaluation_protocol_hash"],
        }

    async def attach_run_to_evaluation(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            if len(targets) != 1:
                raise ConflictError(
                    "Only single-target Runs can be attached to the Evaluation catalog"
                )
            target = targets[0]
            suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            identity_hash = target_identity_hash(
                target_type=target.target_type,
                entity_id=target.entity_id,
                source_type=target.source_type,
                target_version_id=_target_version_id(target),
                snapshot_hash=target.snapshot_hash,
            )
            protocol_hash = evaluation_protocol_hash(suite)
            evaluation = await session.scalar(
                select(EvaluationModel).where(
                    EvaluationModel.project_id == project_id,
                    EvaluationModel.suite_version_id == run.suite_version_id,
                    EvaluationModel.target_identity_hash == identity_hash,
                )
            )
            if evaluation is None:
                evaluation = EvaluationModel(
                    project_id=project_id,
                    suite_version_id=run.suite_version_id,
                    target_type=target.target_type,
                    entity_id=target.entity_id,
                    source_type=target.source_type,
                    target_version_id=_target_version_id(target),
                    target_snapshot_hash=target.snapshot_hash,
                    target_identity_hash=identity_hash,
                    display_name=target.display_name,
                    display_version=target.display_version,
                    status="active",
                    latest_run_id=run.id,
                    created_by=created_by,
                )
                session.add(evaluation)
                await session.flush()
            else:
                evaluation.latest_run_id = run.id
                evaluation.display_name = target.display_name
                evaluation.display_version = target.display_version
            await session.execute(
                text(
                    "UPDATE evaluation.runs "
                    "SET evaluation_id = :evaluation_id, evaluation_protocol_hash = :protocol_hash "
                    "WHERE id = :run_id AND project_id = :project_id"
                ),
                {
                    "evaluation_id": evaluation.id,
                    "protocol_hash": protocol_hash,
                    "run_id": run.id,
                    "project_id": project_id,
                },
            )
            return self._evaluation_payload(evaluation, run_count=None, protocol_hash=protocol_hash)

    async def list_evaluations(
        self,
        *,
        project_id: UUID,
        target_type: str | None = None,
        entity_id: UUID | None = None,
        suite_version_id: UUID | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            statement = select(EvaluationModel).where(EvaluationModel.project_id == project_id)
            if not include_archived:
                statement = statement.where(EvaluationModel.status != "archived")
            if target_type:
                statement = statement.where(EvaluationModel.target_type == target_type)
            if entity_id:
                statement = statement.where(EvaluationModel.entity_id == entity_id)
            if suite_version_id:
                statement = statement.where(
                    EvaluationModel.suite_version_id == suite_version_id
                )
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(EvaluationModel.updated_at.desc()).limit(500)
                    )
                ).all()
            )
            result: list[dict[str, Any]] = []
            for row in rows:
                run_count = int(
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) FROM evaluation.runs "
                                "WHERE evaluation_id = :evaluation_id"
                            ),
                            {"evaluation_id": row.id},
                        )
                    ).scalar_one()
                )
                latest = (
                    await session.get(EvaluationRunModel, row.latest_run_id)
                    if row.latest_run_id
                    else None
                )
                protocol_hash = None
                if latest is not None:
                    protocol_hash = (
                        await session.execute(
                            text(
                                "SELECT evaluation_protocol_hash FROM evaluation.runs "
                                "WHERE id = :run_id"
                            ),
                            {"run_id": latest.id},
                        )
                    ).scalar_one_or_none()
                item = self._evaluation_payload(
                    row,
                    run_count=run_count,
                    protocol_hash=protocol_hash,
                )
                item["latest_run"] = self._run_summary(latest) if latest else None
                result.append(item)
            return result

    async def get_evaluation(
        self,
        *,
        project_id: UUID,
        evaluation_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            evaluation = await session.get(EvaluationModel, evaluation_id)
            if evaluation is None or evaluation.project_id != project_id:
                raise NotFoundError("Evaluation not found")
            run_ids = list(
                (
                    await session.execute(
                        text(
                            "SELECT id, evaluation_protocol_hash FROM evaluation.runs "
                            "WHERE evaluation_id = :evaluation_id "
                            "ORDER BY created_at DESC"
                        ),
                        {"evaluation_id": evaluation.id},
                    )
                ).all()
            )
            runs: list[dict[str, Any]] = []
            protocol_hash = None
            for row in run_ids:
                run = await session.get(EvaluationRunModel, row.id)
                if run is not None:
                    runs.append(self._run_summary(run))
                    protocol_hash = protocol_hash or row.evaluation_protocol_hash
            payload = self._evaluation_payload(
                evaluation,
                run_count=len(runs),
                protocol_hash=protocol_hash,
            )
            payload["runs"] = runs
            payload["latest_run"] = runs[0] if runs else None
            return payload

    async def archive_evaluation(
        self,
        *,
        project_id: UUID,
        evaluation_id: UUID,
        archived_by: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationModel, evaluation_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation not found")
            row.status = "archived"
            row.archived_at = datetime.now(timezone.utc)
            row.archived_by = archived_by
            return self._evaluation_payload(row, run_count=None, protocol_hash=None)

    async def restore_evaluation(
        self,
        *,
        project_id: UUID,
        evaluation_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationModel, evaluation_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation not found")
            row.status = "active"
            row.archived_at = None
            row.archived_by = None
            return self._evaluation_payload(row, run_count=None, protocol_hash=None)

    async def preview_comparison(
        self,
        *,
        project_id: UUID,
        candidate_run_id: UUID,
        reference_run_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            candidate = await self._load_run(session, project_id, candidate_run_id)
            reference = await self._load_run(session, project_id, reference_run_id)
            candidate_hash = await self._protocol_for_run(session, candidate)
            reference_hash = await self._protocol_for_run(session, reference)
            compatibility = protocol_compatibility(
                candidate_hash,
                reference_hash,
                candidate_repetitions=candidate.repetitions,
                reference_repetitions=reference.repetitions,
            )
            return {
                **compatibility,
                "candidate": self._run_summary(candidate),
                "reference": self._run_summary(reference),
                "protocol_hash": candidate_hash if compatibility["compatible"] else None,
                "executes_targets": False,
                "executes_judges": False,
            }

    async def create_comparison_from_runs(
        self,
        *,
        project_id: UUID,
        candidate_run_id: UUID,
        reference_run_id: UUID,
        candidate_revision: int | None,
        reference_revision: int | None,
        requested_by: UUID | None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if candidate_run_id == reference_run_id:
            raise ValidationError("Comparison requires two different Evaluation Runs")
        async with self._session_factory() as session, session.begin():
            candidate = await self._load_run(session, project_id, candidate_run_id)
            reference = await self._load_run(session, project_id, reference_run_id)
            candidate_hash = await self._protocol_for_run(session, candidate)
            reference_hash = await self._protocol_for_run(session, reference)
            compatibility = protocol_compatibility(
                candidate_hash,
                reference_hash,
                candidate_repetitions=candidate.repetitions,
                reference_repetitions=reference.repetitions,
            )
            if not compatibility["compatible"]:
                raise ConflictError(
                    "The selected Runs used different Evaluation protocols and cannot produce a quantitative Comparison"
                )
            if candidate.suite_version_id != reference.suite_version_id:
                raise ConflictError("Comparison requires the same immutable Suite Version")
            c_revision = candidate_revision or _revision(candidate)
            r_revision = reference_revision or _revision(reference)
            normalized_key = idempotency_key.strip() if idempotency_key else None
            if normalized_key:
                existing = await session.scalar(
                    select(EvaluationComparisonModel).where(
                        EvaluationComparisonModel.project_id == project_id,
                        EvaluationComparisonModel.request_idempotency_key == normalized_key,
                    )
                )
                if existing is not None:
                    await self._refresh_comparison(session, existing)
                    return await self._comparison_payload(session, existing)
            existing_pair = await session.scalar(
                select(EvaluationComparisonModel).where(
                    EvaluationComparisonModel.candidate_run_id == candidate.id,
                    EvaluationComparisonModel.candidate_evidence_revision == c_revision,
                    EvaluationComparisonModel.reference_run_id == reference.id,
                    EvaluationComparisonModel.reference_evidence_revision == r_revision,
                )
            )
            if existing_pair is not None:
                await self._refresh_comparison(session, existing_pair)
                return await self._comparison_payload(session, existing_pair)
            comparison = EvaluationComparisonModel(
                project_id=project_id,
                suite_version_id=candidate.suite_version_id,
                protocol_hash=str(candidate_hash),
                comparison_mode=(
                    "paired"
                    if candidate.repetitions == reference.repetitions
                    else "post_hoc"
                ),
                candidate_run_id=candidate.id,
                candidate_evidence_revision=c_revision,
                reference_run_id=reference.id,
                reference_evidence_revision=r_revision,
                status="waiting",
                request_idempotency_key=normalized_key,
                requested_by=requested_by,
            )
            session.add(comparison)
            await session.flush()
            await self._refresh_comparison(session, comparison)
            return await self._comparison_payload(session, comparison)

    async def create_paired_comparison(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        candidate: dict[str, Any],
        reference: dict[str, Any],
        requested_by: UUID | None,
        acknowledge_tool_side_effects: bool,
        approved_high_risk_tool_ids: list[UUID],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not idempotency_key or len(idempotency_key.strip()) < 8:
            raise ValidationError("Paired Comparison requires an idempotency key")
        candidate_run = await self.create_evaluation_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            target=candidate,
            requested_by=requested_by,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids,
            idempotency_key=f"{idempotency_key}:candidate",
        )
        reference_run = await self.create_evaluation_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            target=reference,
            requested_by=requested_by,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids,
            idempotency_key=f"{idempotency_key}:reference",
        )
        comparison = await self.create_comparison_from_runs(
            project_id=project_id,
            candidate_run_id=UUID(str(candidate_run["id"])),
            reference_run_id=UUID(str(reference_run["id"])),
            candidate_revision=1,
            reference_revision=1,
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )
        comparison["created_runs"] = {
            "candidate": candidate_run,
            "reference": reference_run,
        }
        return comparison

    async def list_comparisons(
        self,
        *,
        project_id: UUID,
        entity_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session, session.begin():
            rows = list(
                (
                    await session.scalars(
                        select(EvaluationComparisonModel)
                        .where(EvaluationComparisonModel.project_id == project_id)
                        .order_by(EvaluationComparisonModel.created_at.desc())
                        .limit(300)
                    )
                ).all()
            )
            result: list[dict[str, Any]] = []
            for row in rows:
                if entity_id is not None:
                    candidate_target = await self._single_target(session, row.candidate_run_id)
                    reference_target = await self._single_target(session, row.reference_run_id)
                    if entity_id not in {
                        candidate_target.entity_id if candidate_target else None,
                        reference_target.entity_id if reference_target else None,
                    }:
                        continue
                await self._refresh_comparison(session, row)
                result.append(await self._comparison_payload(session, row))
            return result

    async def get_comparison(
        self,
        *,
        project_id: UUID,
        comparison_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationComparisonModel, comparison_id, with_for_update=True)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Comparison not found")
            await self._refresh_comparison(session, row)
            payload = await self._comparison_payload(session, row)
        payload["candidate_run"] = await self._runs.get_run(project_id, row.candidate_run_id)
        payload["reference_run"] = await self._runs.get_run(project_id, row.reference_run_id)
        return payload

    async def create_comparison_decision(
        self,
        *,
        project_id: UUID,
        comparison_id: UUID,
        decision: str,
        decision_basis: str,
        note: str | None,
        decided_by: UUID,
    ) -> dict[str, Any]:
        allowed = {"select_candidate", "keep_reference", "no_preference"}
        if decision not in allowed:
            raise ValidationError("Comparison decision is invalid")
        if decision_basis not in {"evidence", "manual_override"}:
            raise ValidationError("Comparison decision basis is invalid")
        normalized_note = note.strip() if isinstance(note, str) and note.strip() else None
        async with self._session_factory() as session, session.begin():
            comparison = await session.get(
                EvaluationComparisonModel,
                comparison_id,
                with_for_update=True,
            )
            if comparison is None or comparison.project_id != project_id:
                raise NotFoundError("Evaluation Comparison not found")
            await self._refresh_comparison(session, comparison)
            if comparison.status != "ready" and decision_basis != "manual_override":
                raise ConflictError(
                    "A normal selection requires two conclusive Evaluation results"
                )
            if comparison.status != "ready" and not normalized_note:
                raise ValidationError("Manual override requires a decision note")
            existing = await session.scalar(
                select(EvaluationComparisonDecisionModel).where(
                    EvaluationComparisonDecisionModel.comparison_id == comparison.id,
                    EvaluationComparisonDecisionModel.candidate_evidence_revision
                    == comparison.candidate_evidence_revision,
                    EvaluationComparisonDecisionModel.reference_evidence_revision
                    == comparison.reference_evidence_revision,
                )
            )
            now = datetime.now(timezone.utc)
            if existing is None:
                existing = EvaluationComparisonDecisionModel(
                    project_id=project_id,
                    comparison_id=comparison.id,
                    candidate_evidence_revision=comparison.candidate_evidence_revision,
                    reference_evidence_revision=comparison.reference_evidence_revision,
                    decision=decision,
                    decision_basis=decision_basis,
                    note=normalized_note,
                    decided_by=decided_by,
                    decided_at=now,
                )
                session.add(existing)
            else:
                existing.decision = decision
                existing.decision_basis = decision_basis
                existing.note = normalized_note
                existing.decided_by = decided_by
                existing.decided_at = now
            await session.flush()
            return self._comparison_decision_payload(existing)

    async def _refresh_comparison(self, session, comparison: EvaluationComparisonModel) -> None:
        candidate = await self._load_run(session, comparison.project_id, comparison.candidate_run_id)
        reference = await self._load_run(session, comparison.project_id, comparison.reference_run_id)
        if candidate.status in _ACTIVE_RUN_STATUSES or reference.status in _ACTIVE_RUN_STATUSES:
            comparison.status = "running" if (
                candidate.status not in {"queued", "snapshotting"}
                or reference.status not in {"queued", "snapshotting"}
            ) else "waiting"
            comparison.aggregate_result = {
                "candidate": self._run_summary(candidate),
                "reference": self._run_summary(reference),
                "comparison_available": False,
                "reason": "evaluation_runs_in_progress",
            }
            return

        candidate_hash = await self._protocol_for_run(session, candidate)
        reference_hash = await self._protocol_for_run(session, reference)
        compatibility = protocol_compatibility(
            candidate_hash,
            reference_hash,
            candidate_repetitions=candidate.repetitions,
            reference_repetitions=reference.repetitions,
        )
        if not compatibility["compatible"]:
            comparison.status = "incompatible"
            comparison.failure_code = str(compatibility["reason"])
            comparison.failure_detail = " ".join(compatibility["warnings"])
            comparison.aggregate_result = {"compatibility": compatibility}
            comparison.completed_at = datetime.now(timezone.utc)
            return

        c_target = await self._single_target(session, candidate.id)
        r_target = await self._single_target(session, reference.id)
        c_trials = await self._trials(session, candidate.id)
        r_trials = await self._trials(session, reference.id)
        c_summary = _summary_for(candidate, c_target.id if c_target else None)
        r_summary = _summary_for(reference, r_target.id if r_target else None)
        c_score = c_summary.get("weighted_score")
        r_score = r_summary.get("weighted_score")
        c_pass = c_summary.get("weighted_pass_rate")
        r_pass = r_summary.get("weighted_pass_rate")
        c_runtime = _target_runtime_metrics(c_trials)
        r_runtime = _target_runtime_metrics(r_trials)
        c_failures = await self._failure_summary(session, candidate.id, c_trials)
        r_failures = await self._failure_summary(session, reference.id, r_trials)
        per_case = await self._case_comparison(session, c_trials, r_trials)
        wins = sum(1 for item in per_case if item.get("winner") == "candidate")
        losses = sum(1 for item in per_case if item.get("winner") == "reference")
        ties = sum(1 for item in per_case if item.get("winner") == "tie")

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
            "The target outputs are preserved, but one or both Evaluations lack scored Judge evidence."
            if reason
            else None
        )
        comparison.completed_at = (
            datetime.now(timezone.utc) if status in {"ready", "partial", "blocked"} else None
        )
        comparison.aggregate_result = {
            "comparison_available": status == "ready",
            "comparison_kind": compatibility["comparison_kind"],
            "compatibility": compatibility,
            "candidate": {
                "run": self._run_summary(candidate),
                "target": self._target_payload(c_target),
                "summary": c_summary,
                "runtime": c_runtime,
                "failures": c_failures,
            },
            "reference": {
                "run": self._run_summary(reference),
                "target": self._target_payload(r_target),
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
                "unavailable": len(per_case) - wins - losses - ties,
            },
            "cases": per_case,
            "reason": reason,
        }

    async def _case_comparison(
        self,
        session,
        candidate_trials: list[EvaluationTrialModel],
        reference_trials: list[EvaluationTrialModel],
    ) -> list[dict[str, Any]]:
        case_ids = {item.test_case_id for item in candidate_trials + reference_trials}
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

        def grouped(values: list[EvaluationTrialModel]) -> dict[UUID, list[EvaluationTrialModel]]:
            result: dict[UUID, list[EvaluationTrialModel]] = {}
            for trial in values:
                result.setdefault(trial.test_case_id, []).append(trial)
            return result

        c_groups = grouped(candidate_trials)
        r_groups = grouped(reference_trials)
        result: list[dict[str, Any]] = []
        for case_id in sorted(case_ids, key=lambda value: cases.get(value).position if cases.get(value) else 0):
            c_values = c_groups.get(case_id, [])
            r_values = r_groups.get(case_id, [])
            c_scores = [float(item.score) for item in c_values if item.score is not None]
            r_scores = [float(item.score) for item in r_values if item.score is not None]
            c_average = sum(c_scores) / len(c_scores) if c_scores else None
            r_average = sum(r_scores) / len(r_scores) if r_scores else None
            winner = None
            if c_average is not None and r_average is not None:
                delta = c_average - r_average
                winner = "tie" if abs(delta) < 0.001 else (
                    "candidate" if delta > 0 else "reference"
                )
            else:
                delta = None
            case = cases.get(case_id)
            result.append(
                {
                    "test_case_id": str(case_id),
                    "name": case.name if case else str(case_id),
                    "case_type": case.case_type if case else None,
                    "candidate": {
                        "score": c_average,
                        "passed": sum(1 for item in c_values if item.passed is True),
                        "total": len(c_values),
                        "conclusive": len(c_scores),
                    },
                    "reference": {
                        "score": r_average,
                        "passed": sum(1 for item in r_values if item.passed is True),
                        "total": len(r_values),
                        "conclusive": len(r_scores),
                    },
                    "score_delta": delta,
                    "winner": winner,
                }
            )
        return result

    async def _failure_summary(
        self,
        session,
        run_id: UUID,
        trials: list[EvaluationTrialModel],
    ) -> dict[str, Any]:
        calls = list(
            (
                await session.scalars(
                    select(EvaluatorModelCallModel).where(
                        EvaluatorModelCallModel.evaluation_run_id == run_id
                    )
                )
            ).all()
        )
        return summarize_failures(
            [
                {
                    "id": str(item.id),
                    "status": item.status,
                    "failure_code": item.failure_code,
                    "failure_detail": item.failure_detail,
                    "metrics": item.metrics or {},
                }
                for item in trials
            ],
            [
                {
                    "trial_id": str(item.evaluation_trial_id),
                    "status": item.status,
                    "error": item.error,
                }
                for item in calls
            ],
        )

    async def _comparison_payload(self, session, row: EvaluationComparisonModel) -> dict[str, Any]:
        decisions = list(
            (
                await session.scalars(
                    select(EvaluationComparisonDecisionModel)
                    .where(EvaluationComparisonDecisionModel.comparison_id == row.id)
                    .order_by(EvaluationComparisonDecisionModel.decided_at.desc())
                )
            ).all()
        )
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "suite_version_id": str(row.suite_version_id),
            "protocol_hash": row.protocol_hash,
            "comparison_mode": row.comparison_mode,
            "status": row.status,
            "candidate_run_id": str(row.candidate_run_id),
            "candidate_evidence_revision": row.candidate_evidence_revision,
            "reference_run_id": str(row.reference_run_id),
            "reference_evidence_revision": row.reference_evidence_revision,
            "aggregate_result": row.aggregate_result,
            "failure_code": row.failure_code,
            "failure_detail": row.failure_detail,
            "decision": self._comparison_decision_payload(decisions[0]) if decisions else None,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "completed_at": row.completed_at,
        }

    @staticmethod
    def _comparison_decision_payload(row: EvaluationComparisonDecisionModel) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "comparison_id": str(row.comparison_id),
            "candidate_evidence_revision": row.candidate_evidence_revision,
            "reference_evidence_revision": row.reference_evidence_revision,
            "decision": row.decision,
            "decision_basis": row.decision_basis,
            "note": row.note,
            "decided_by": str(row.decided_by),
            "decided_at": row.decided_at,
        }

    @staticmethod
    def _evaluation_payload(
        row: EvaluationModel,
        *,
        run_count: int | None,
        protocol_hash: str | None,
    ) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "suite_version_id": str(row.suite_version_id),
            "target_type": row.target_type,
            "entity_id": str(row.entity_id),
            "source_type": row.source_type,
            "target_version_id": str(row.target_version_id) if row.target_version_id else None,
            "target_snapshot_hash": row.target_snapshot_hash,
            "target_identity_hash": row.target_identity_hash,
            "display_name": row.display_name,
            "display_version": row.display_version,
            "status": row.status,
            "latest_run_id": str(row.latest_run_id) if row.latest_run_id else None,
            "run_count": run_count,
            "evaluation_protocol_hash": protocol_hash,
            "archived_at": row.archived_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _run_summary(run: EvaluationRunModel | None) -> dict[str, Any] | None:
        if run is None:
            return None
        return {
            "id": str(run.id),
            "suite_version_id": str(run.suite_version_id),
            "status": run.status,
            "mode": run.mode,
            "repetitions": run.repetitions,
            "evidence_revision": _revision(run),
            "assessment_status": _assessment(run),
            "overall_score": run.overall_score,
            "pass_rate": run.pass_rate,
            "measured_total_cost": float(run.measured_total_cost)
            if run.measured_total_cost is not None
            else None,
            "failure_code": run.failure_code,
            "failure_detail": run.failure_detail,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "created_at": run.created_at,
        }

    @staticmethod
    def _target_payload(target: EvaluationTargetModel | None) -> dict[str, Any] | None:
        if target is None:
            return None
        return {
            "id": str(target.id),
            "target_type": target.target_type,
            "source_type": target.source_type,
            "entity_id": str(target.entity_id),
            "environment": target.environment,
            "snapshot_hash": target.snapshot_hash,
            "display_name": target.display_name,
            "display_version": target.display_version,
            "agent_release_id": str(target.agent_release_id) if target.agent_release_id else None,
            "network_version_id": str(target.network_version_id) if target.network_version_id else None,
        }

    async def _load_run(self, session, project_id: UUID, run_id: UUID) -> EvaluationRunModel:
        run = await session.get(EvaluationRunModel, run_id)
        if run is None or run.project_id != project_id:
            raise NotFoundError("Evaluation Run not found")
        return run

    async def _protocol_for_run(self, session, run: EvaluationRunModel) -> str:
        value = (
            await session.execute(
                text(
                    "SELECT evaluation_protocol_hash FROM evaluation.runs WHERE id = :run_id"
                ),
                {"run_id": run.id},
            )
        ).scalar_one_or_none()
        if value:
            return str(value)
        suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
        if suite is None:
            raise NotFoundError("Evaluation Suite version not found")
        value = evaluation_protocol_hash(suite)
        await session.execute(
            text(
                "UPDATE evaluation.runs SET evaluation_protocol_hash = :value WHERE id = :run_id"
            ),
            {"value": value, "run_id": run.id},
        )
        return value

    async def _single_target(self, session, run_id: UUID) -> EvaluationTargetModel | None:
        values = list(
            (
                await session.scalars(
                    select(EvaluationTargetModel).where(
                        EvaluationTargetModel.evaluation_run_id == run_id
                    )
                )
            ).all()
        )
        return values[0] if len(values) == 1 else None

    async def _trials(self, session, run_id: UUID) -> list[EvaluationTrialModel]:
        return list(
            (
                await session.scalars(
                    select(EvaluationTrialModel)
                    .where(EvaluationTrialModel.evaluation_run_id == run_id)
                    .order_by(EvaluationTrialModel.execution_order)
                )
            ).all()
        )


__all__ = ["EvaluationCatalogService"]
