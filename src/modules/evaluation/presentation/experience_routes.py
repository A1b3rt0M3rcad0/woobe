from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modules.evaluation.application.governed_run_diagnostics import (
    GovernedEvaluationRunDiagnosticsService,
)
from modules.evaluation.application.judge_policy import JudgePreflightService
from modules.evaluation.application.revision_aware_experience import (
    RevisionAwareEvaluationExperienceService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class RetryJudgmentsRequest(BaseModel):
    trial_ids: list[UUID] = Field(default_factory=list, max_length=5000)
    failure_codes: list[str] = Field(default_factory=list, max_length=50)


class ChangeSuiteJudgeModelRequest(BaseModel):
    judge_model_id: UUID
    change_description: str = Field(min_length=3, max_length=2000)


@router.get("/judge-models")
async def list_evaluation_judge_models(
    project_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    async with request.app.state.session_factory() as session:
        data = await JudgePreflightService().list_models(
            session,
            project_id=project_id,
        )
    return {"success": True, "data": data}


@router.post("/suites/{suite_id}/judge-model")
async def change_evaluation_suite_judge_model(
    project_id: UUID,
    suite_id: UUID,
    payload: ChangeSuiteJudgeModelRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    service = RevisionAwareEvaluationExperienceService(
        request.app.state.session_factory
    )
    return {
        "success": True,
        "data": await service.create_judge_model_suite_version(
            project_id=project_id,
            suite_id=suite_id,
            judge_provider_model_id=payload.judge_model_id,
            change_description=payload.change_description,
            created_by=user_id,
        ),
    }


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


@router.get("/runs/{run_id}/diagnostics")
async def get_evaluation_run_diagnostics(
    project_id: UUID,
    run_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    service = GovernedEvaluationRunDiagnosticsService(
        request.app.state.session_factory
    )
    return {
        "success": True,
        "data": await service.get_run_diagnostics(
            project_id=project_id,
            run_id=run_id,
        ),
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
