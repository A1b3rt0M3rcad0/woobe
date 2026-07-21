from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request

from modules.evaluation.application.completed_service import (
    CompletedEvaluationApplicationService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


def _service(request: Request) -> CompletedEvaluationApplicationService:
    return CompletedEvaluationApplicationService(request.app.state.session_factory)


@router.get("/datasets/page")
async def list_datasets_page(
    project_id: UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    include_archived: bool = False,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_datasets_page(
            project_id,
            limit=limit,
            cursor=cursor,
            include_archived=include_archived,
        ),
    }


@router.get("/suites/page")
async def list_suites_page(
    project_id: UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    include_archived: bool = False,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_suites_page(
            project_id,
            limit=limit,
            cursor=cursor,
            include_archived=include_archived,
        ),
    }


__all__ = ["router"]
