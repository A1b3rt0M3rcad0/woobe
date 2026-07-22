from __future__ import annotations

from typing import Any

from modules.evaluation.application.evidence_revision_snapshot import revision_number
from modules.evaluation.application.revision_comparison_service import (
    RevisionComparisonCatalogService,
)


class OperationalEvaluationCatalogService(RevisionComparisonCatalogService):
    """Final catalog facade with JSON-safe operational payloads."""

    @staticmethod
    def _run_summary(run) -> dict[str, Any] | None:
        if run is None:
            return None
        aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
        assessment = aggregate.get("assessment")
        assessment = assessment if isinstance(assessment, dict) else {}
        return {
            "id": str(run.id),
            "suite_version_id": str(run.suite_version_id),
            "status": run.status,
            "mode": run.mode,
            "repetitions": run.repetitions,
            "evidence_revision": revision_number(run),
            "assessment_status": assessment.get("status") or (
                "pending"
                if run.status in {
                    "queued",
                    "snapshotting",
                    "executing",
                    "judging",
                    "aggregating",
                    "cancel_requested",
                }
                else "inconclusive"
            ),
            "overall_score": run.overall_score,
            "pass_rate": run.pass_rate,
            "measured_total_cost": float(run.measured_total_cost)
            if run.measured_total_cost is not None
            else None,
            "failure_code": run.failure_code,
            "failure_detail": run.failure_detail,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }


__all__ = ["OperationalEvaluationCatalogService"]
