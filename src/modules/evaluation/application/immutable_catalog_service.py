from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from modules.evaluation.application.catalog_service import (
    EvaluationCatalogService,
    _revision,
)
from modules.evaluation.infra.database.catalog_models import (
    EvaluationComparisonModel,
)


class ImmutableEvaluationCatalogService(EvaluationCatalogService):
    """Keep every Comparison bound to the exact evidence revisions selected."""

    async def _refresh_comparison(
        self,
        session,
        comparison: EvaluationComparisonModel,
    ) -> None:
        # A completed Comparison is immutable. A later retry can be compared by
        # creating a new Comparison that references the newer revision.
        if comparison.completed_at is not None and isinstance(
            comparison.aggregate_result,
            dict,
        ):
            return

        candidate = await self._load_run(
            session,
            comparison.project_id,
            comparison.candidate_run_id,
        )
        reference = await self._load_run(
            session,
            comparison.project_id,
            comparison.reference_run_id,
        )
        candidate_revision = _revision(candidate)
        reference_revision = _revision(reference)
        if (
            candidate_revision != comparison.candidate_evidence_revision
            or reference_revision != comparison.reference_evidence_revision
        ):
            comparison.status = "blocked"
            comparison.failure_code = "comparison_evidence_revision_changed"
            comparison.failure_detail = (
                "One of the selected Evaluation Runs moved to a newer evidence "
                "revision before this Comparison became final. Create a new "
                "Comparison for the current revisions."
            )
            comparison.aggregate_result = {
                "comparison_available": False,
                "reason": "comparison_evidence_revision_changed",
                "selected_revisions": {
                    "candidate": comparison.candidate_evidence_revision,
                    "reference": comparison.reference_evidence_revision,
                },
                "current_revisions": {
                    "candidate": candidate_revision,
                    "reference": reference_revision,
                },
            }
            comparison.completed_at = datetime.now(timezone.utc)
            return
        await super()._refresh_comparison(session, comparison)

    async def create_comparison_from_runs(self, **kwargs):
        payload = await super().create_comparison_from_runs(**kwargs)
        comparison_id = UUID(str(payload["id"]))
        async with self._session_factory() as session, session.begin():
            row = await session.get(
                EvaluationComparisonModel,
                comparison_id,
                with_for_update=True,
            )
            if row is not None:
                row.comparison_mode = "post_hoc"
        payload["comparison_mode"] = "post_hoc"
        return payload

    async def create_paired_comparison(self, **kwargs):
        payload = await super().create_paired_comparison(**kwargs)
        comparison_id = UUID(str(payload["id"]))
        async with self._session_factory() as session, session.begin():
            row = await session.get(
                EvaluationComparisonModel,
                comparison_id,
                with_for_update=True,
            )
            if row is not None:
                row.comparison_mode = "paired"
        payload["comparison_mode"] = "paired"
        return payload


__all__ = ["ImmutableEvaluationCatalogService"]
