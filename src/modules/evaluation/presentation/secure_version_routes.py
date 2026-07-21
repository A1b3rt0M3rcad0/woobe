from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from modules.evaluation.application.final_service import FinalEvaluationApplicationService
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class SecureComposedSuiteVersionRequest(BaseModel):
    draft: dict[str, Any]
    change_description: str = Field(min_length=3, max_length=2000)
    judge_provider_model_id: UUID | None = None
    judge_config: dict[str, Any] | None = None
    rubric: dict[str, Any] | None = None
    deterministic_checks: dict[str, Any] | None = None
    acceptance_policy: dict[str, Any] | None = None
    repetition_policy: dict[str, Any] | None = None
    estimate_defaults: dict[str, Any] | None = None
    authoring_source: Literal["manual", "json_import", "ai_generated"] = "manual"
    source_snapshot_hash: str | None = Field(default=None, max_length=64)
    source_context_hash: str | None = Field(default=None, max_length=64)
    authoring_metadata: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/suites/{suite_id}/versions/composed",
    status_code=status.HTTP_201_CREATED,
)
async def create_secure_composed_suite_version(
    project_id: UUID,
    suite_id: UUID,
    payload: SecureComposedSuiteVersionRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    service = FinalEvaluationApplicationService(request.app.state.session_factory)
    data = await service.create_composed_suite_version(
        project_id=project_id,
        suite_id=suite_id,
        draft=payload.draft,
        change_description=payload.change_description,
        judge_provider_model_id=payload.judge_provider_model_id,
        judge_config=payload.judge_config,
        rubric=payload.rubric,
        deterministic_checks=payload.deterministic_checks,
        acceptance_policy=payload.acceptance_policy,
        repetition_policy=payload.repetition_policy,
        estimate_defaults=payload.estimate_defaults,
        authoring_source=payload.authoring_source,
        source_snapshot_hash=payload.source_snapshot_hash,
        source_context_hash=payload.source_context_hash,
        authoring_metadata=payload.authoring_metadata,
        created_by=user_id,
    )
    return {"success": True, "data": data}


__all__ = ["router"]
