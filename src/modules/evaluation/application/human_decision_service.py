from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.completed_service import (
    CompletedEvaluationApplicationService,
)
from modules.evaluation.infra.database.decision_models import (
    EvaluationTargetDecisionModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import ConflictError, NotFoundError, ValidationError

_TERMINAL_RUN_STATUSES = {
    "completed",
    "partially_completed",
    "failed",
    "cancelled",
}


def _aggregate(run: EvaluationRunModel) -> dict[str, Any]:
    return run.aggregate_result if isinstance(run.aggregate_result, dict) else {}


def _evidence_revision(run: EvaluationRunModel) -> int:
    try:
        return max(1, int(_aggregate(run).get("evidence_revision") or 1))
    except (TypeError, ValueError):
        return 1


def _assessment_hash(run: EvaluationRunModel) -> str:
    aggregate = _aggregate(run)
    return canonical_hash(
        {
            "evidence_revision": _evidence_revision(run),
            "assessment": aggregate.get("assessment"),
            "target_summaries": aggregate.get("target_summaries"),
        }
    )


def _assessment_status(run: EvaluationRunModel) -> str | None:
    assessment = _aggregate(run).get("assessment")
    if isinstance(assessment, dict) and isinstance(assessment.get("status"), str):
        return str(assessment["status"])
    legacy = run.qualification_status
    if legacy in {"qualified", "qualified_with_warnings"}:
        return "meets_policy"
    if legacy == "not_qualified":
        return "below_policy"
    if legacy == "inconclusive":
        return "inconclusive"
    return None


def _tool_manifest(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = snapshot.get("runtime_config")
    runtime = runtime if isinstance(runtime, dict) else {}
    tools = runtime.get("tools")
    tools = tools if isinstance(tools, dict) else {}
    raw_snapshots = tools.get("snapshots")
    values: list[dict[str, Any]] = []
    if isinstance(raw_snapshots, list):
        values = [item for item in raw_snapshots if isinstance(item, dict)]
    elif isinstance(raw_snapshots, dict):
        values = [item for item in raw_snapshots.values() if isinstance(item, dict)]
    result = []
    for item in values:
        result.append(
            {
                "id": str(item.get("id") or item.get("tool_id") or "") or None,
                "name": str(item.get("name") or item.get("tool_name") or "Tool"),
                "type": item.get("type") or item.get("tool_type"),
                "risk_level": item.get("risk_level"),
                "snapshot_hash": item.get("snapshot_hash") or canonical_hash(item),
            }
        )
    if result:
        return result
    return [
        {"id": str(value), "name": "Tool", "snapshot_hash": None}
        for value in tools.get("tool_ids", [])
    ]


def _target_manifest(target: EvaluationTargetModel) -> dict[str, Any]:
    snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
    if target.target_type == "network":
        definition = snapshot.get("definition")
        definition = definition if isinstance(definition, dict) else {}
        bindings = snapshot.get("resolved_bindings")
        return {
            "identity": {
                "target_type": "network",
                "name": target.display_name,
                "environment": target.environment,
                "version": target.display_version,
                "snapshot_hash": target.snapshot_hash,
                "composition_hash": target.composition_hash,
                "network_version_id": str(target.network_version_id)
                if target.network_version_id
                else None,
            },
            "network": {
                "node_count": len(definition.get("nodes") or []),
                "edge_count": len(definition.get("edges") or []),
                "binding_count": len(bindings or {})
                if isinstance(bindings, (dict, list))
                else 0,
                "timeout_seconds": snapshot.get("timeout_seconds"),
            },
        }

    system_prompt = str(snapshot.get("system_prompt") or "")
    output_schema = snapshot.get("output_schema")
    runtime = snapshot.get("runtime_config")
    runtime = runtime if isinstance(runtime, dict) else {}
    return {
        "identity": {
            "target_type": "agent",
            "name": target.display_name,
            "environment": target.environment,
            "version": target.display_version,
            "snapshot_hash": target.snapshot_hash,
            "release_id": str(target.agent_release_id) if target.agent_release_id else None,
        },
        "model": {
            "provider": snapshot.get("provider"),
            "model": snapshot.get("model"),
            "provider_model_id": snapshot.get("provider_model_id"),
            "fallback_provider": snapshot.get("fallback_provider"),
            "fallback_model": snapshot.get("fallback_model"),
        },
        "prompt": {
            "hash": canonical_hash(system_prompt),
            "characters": len(system_prompt),
        },
        "tools": _tool_manifest(snapshot),
        "knowledge": {
            "collection_ids": [str(value) for value in snapshot.get("collection_ids") or []],
            "vector_snapshot_id": runtime.get("vector_snapshot_id"),
        },
        "output_contract": {
            "response_format": snapshot.get("response_format"),
            "schema_hash": canonical_hash(output_schema) if output_schema else None,
            "has_schema": bool(output_schema),
        },
        "runtime": {
            "temperature": snapshot.get("temperature"),
            "max_output_tokens": snapshot.get("max_output_tokens"),
            "session_mode": snapshot.get("session_mode"),
        },
    }


class HumanDecisionEvaluationApplicationService(
    CompletedEvaluationApplicationService
):
    """Expose policy assessment separately from explicit human decisions."""

    async def _resolve_target_dict(
        self,
        session,
        *,
        project_id: UUID,
        raw: dict[str, Any] | None,
    ):
        if isinstance(raw, dict) and raw.get("variant") is not None:
            raise ValidationError(
                "Model overrides are not supported. Evaluate one real snapshot or compare two real snapshots."
            )
        return await super()._resolve_target_dict(
            session,
            project_id=project_id,
            raw=raw,
        )

    @staticmethod
    def _target_payload(target) -> dict[str, Any]:
        return {
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
            "snapshot_hash": target.snapshot_hash,
            "composition_hash": target.composition_hash,
            "display_name": target.display_name,
            "display_version": target.display_version,
            "manifest": _target_manifest(target),
        }

    def _run_payload(self, run, targets) -> dict[str, Any]:
        payload = super()._run_payload(run, targets)
        aggregate = _aggregate(run)
        payload["assessment_status"] = _assessment_status(run)
        payload["evidence_revision"] = _evidence_revision(run)
        payload["judgment_retry"] = aggregate.get("judgment_retry")
        payload["legacy_automatic_qualification"] = bool(
            run.qualification_status
            and not isinstance(aggregate.get("assessment"), dict)
        )
        return payload

    async def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, Any]:
        payload = await super().get_run(project_id, run_id)
        async with self._session_factory() as session:
            decisions = list(
                (
                    await session.scalars(
                        select(EvaluationTargetDecisionModel)
                        .where(
                            EvaluationTargetDecisionModel.project_id == project_id,
                            EvaluationTargetDecisionModel.evaluation_run_id == run_id,
                        )
                        .order_by(
                            EvaluationTargetDecisionModel.evidence_revision.desc(),
                            EvaluationTargetDecisionModel.decided_at.desc(),
                        )
                    )
                ).all()
            )
        payload["decisions"] = [self._decision_payload(item) for item in decisions]
        return payload

    async def create_decision(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        target_id: UUID | None,
        decision: str,
        note: str | None,
        decided_by: UUID,
    ) -> dict[str, Any]:
        if decision not in {"accepted", "rejected"}:
            raise ValidationError("Evaluation decision must be accepted or rejected")
        normalized_note = note.strip() if isinstance(note, str) and note.strip() else None
        if normalized_note and len(normalized_note) > 4000:
            raise ValidationError("Evaluation decision note must not exceed 4000 characters")

        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            if run.status not in _TERMINAL_RUN_STATUSES:
                raise ConflictError("Wait for the Evaluation Run to finish before deciding")

            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            if not targets:
                raise ConflictError("Evaluation Run has no target to decide")
            selected = None
            if target_id is not None:
                selected = next((item for item in targets if item.id == target_id), None)
            else:
                selected = next((item for item in targets if item.side == "single"), None)
                selected = selected or next(
                    (item for item in targets if item.side == "candidate"),
                    None,
                )
            if selected is None:
                raise NotFoundError("Evaluation target not found in this Run")

            evidence_revision = _evidence_revision(run)
            existing = await session.scalar(
                select(EvaluationTargetDecisionModel).where(
                    EvaluationTargetDecisionModel.evaluation_run_id == run.id,
                    EvaluationTargetDecisionModel.target_id == selected.id,
                    EvaluationTargetDecisionModel.evidence_revision == evidence_revision,
                )
            )
            now = datetime.now(timezone.utc)
            if existing is None:
                existing = EvaluationTargetDecisionModel(
                    project_id=project_id,
                    evaluation_run_id=run.id,
                    target_id=selected.id,
                    target_snapshot_hash=selected.snapshot_hash,
                    evidence_revision=evidence_revision,
                    assessment_hash=_assessment_hash(run),
                    decision=decision,
                    note=normalized_note,
                    decided_by=decided_by,
                    decided_at=now,
                    superseded_at=None,
                    superseded_reason=None,
                )
                session.add(existing)
            else:
                existing.target_snapshot_hash = selected.snapshot_hash
                existing.assessment_hash = _assessment_hash(run)
                existing.decision = decision
                existing.note = normalized_note
                existing.decided_by = decided_by
                existing.decided_at = now
                existing.superseded_at = None
                existing.superseded_reason = None
            await session.flush()
            return self._decision_payload(existing)

    async def list_qualifications(
        self,
        *,
        project_id: UUID,
        target_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            statement = (
                select(EvaluationTargetDecisionModel, EvaluationTargetModel, EvaluationRunModel)
                .join(
                    EvaluationTargetModel,
                    EvaluationTargetModel.id == EvaluationTargetDecisionModel.target_id,
                )
                .join(
                    EvaluationRunModel,
                    EvaluationRunModel.id == EvaluationTargetDecisionModel.evaluation_run_id,
                )
                .where(
                    EvaluationTargetDecisionModel.project_id == project_id,
                    EvaluationTargetDecisionModel.superseded_at.is_(None),
                )
            )
            if target_type:
                statement = statement.where(EvaluationTargetModel.target_type == target_type)
            if entity_id:
                statement = statement.where(EvaluationTargetModel.entity_id == entity_id)
            rows = list(
                (
                    await session.execute(
                        statement.order_by(
                            EvaluationTargetDecisionModel.decided_at.desc()
                        ).limit(200)
                    )
                ).all()
            )
            result = []
            for decision_row, target, run in rows:
                suite = await session.get(
                    EvaluationSuiteVersionModel,
                    run.suite_version_id,
                )
                result.append(
                    {
                        "id": str(decision_row.id),
                        "target_type": target.target_type,
                        "entity_id": str(target.entity_id),
                        "target_snapshot_hash": target.snapshot_hash,
                        "agent_release_id": str(target.agent_release_id)
                        if target.agent_release_id
                        else None,
                        "network_version_id": str(target.network_version_id)
                        if target.network_version_id
                        else None,
                        "suite_version_id": str(run.suite_version_id),
                        "dataset_version_id": str(suite.dataset_version_id)
                        if suite
                        else None,
                        "evaluation_run_id": str(run.id),
                        "status": "qualified"
                        if decision_row.decision == "accepted"
                        else "not_qualified",
                        "decision": decision_row.decision,
                        "decision_source": "human",
                        "evidence_revision": decision_row.evidence_revision,
                        "score": run.overall_score,
                        "pass_rate": run.pass_rate,
                        "critical_failures": int(
                            ((_aggregate(run).get("assessment") or {}).get(
                                "critical_failures", 0
                            ))
                        ),
                        "summary": {
                            "assessment_status": _assessment_status(run),
                            "note": decision_row.note,
                        },
                        "created_at": decision_row.decided_at,
                    }
                )
            return result

    async def create_estimate(self, **kwargs) -> list[dict[str, Any]]:
        project_id: UUID = kwargs["project_id"]
        run_id: UUID = kwargs["run_id"]
        async with self._session_factory() as session:
            completed_count = await session.scalar(
                select(EvaluationTrialModel.id)
                .where(
                    EvaluationTrialModel.project_id == project_id,
                    EvaluationTrialModel.evaluation_run_id == run_id,
                    EvaluationTrialModel.status == "completed",
                )
                .limit(1)
            )
            if completed_count is None:
                raise ConflictError(
                    "Operational Estimate requires at least one completed Trial"
                )
        return await super().create_estimate(**kwargs)

    @staticmethod
    def _decision_payload(item: EvaluationTargetDecisionModel) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "evaluation_run_id": str(item.evaluation_run_id),
            "target_id": str(item.target_id),
            "target_snapshot_hash": item.target_snapshot_hash,
            "evidence_revision": item.evidence_revision,
            "assessment_hash": item.assessment_hash,
            "decision": item.decision,
            "note": item.note,
            "decided_by": str(item.decided_by),
            "decided_at": item.decided_at,
            "superseded_at": item.superseded_at,
            "superseded_reason": item.superseded_reason,
        }


__all__ = ["HumanDecisionEvaluationApplicationService"]
