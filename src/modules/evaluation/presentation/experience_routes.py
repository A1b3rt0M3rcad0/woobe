from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modules.evaluation.application.revision_aware_experience import (
    RevisionAwareEvaluationExperienceService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class RetryJudgmentsRequest(BaseModel):
    trial_ids: list[UUID] = Field(default_factory=list, max_length=5000)
    failure_codes: list[str] = Field(default_factory=list, max_length=50)


@router.get("/runs/{run_id}/progress")
async def get_evaluation_run_progress(
    project_id: UUID,
    run_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    service = RevisionAwareEvaluationExperienceService(
        request.app.state.session_factory
    )
    return {
        "success": True,
        "data": await service.get_run_progress(project_id, run_id),
    }


@router.post("/runs/{run_id}/retry-judgments")
async def retry_evaluation_judgments(
    project_id: UUID,
    run_id: UUID,
    payload: RetryJudgmentsRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    service = RevisionAwareEvaluationExperienceService(
        request.app.state.session_factory
    )
    return {
        "success": True,
        "data": await service.retry_judgments(
            project_id=project_id,
            run_id=run_id,
            trial_ids=payload.trial_ids or None,
            failure_codes=payload.failure_codes or None,
        ),
    }


__all__ = ["router"]
