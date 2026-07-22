from __future__ import annotations

from uuid import UUID

from modules.evaluation.application.evidence_revision_snapshot import (
    capture_evidence_revision,
)
from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.infra.database.models import EvaluationRunModel
from shared.infra.errors import NotFoundError


class RevisionAwareEvaluationExperienceService(EvaluationExperienceService):
    """Preserve the current evidence revision before any destructive Judge retry."""

    async def retry_judgments(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        trial_ids: list[UUID] | None = None,
        failure_codes: list[str] | None = None,
    ):
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            await capture_evidence_revision(
                session,
                run,
                reason="before_judgment_retry",
            )
        return await super().retry_judgments(
            project_id=project_id,
            run_id=run_id,
            trial_ids=trial_ids,
            failure_codes=failure_codes,
        )


__all__ = ["RevisionAwareEvaluationExperienceService"]
