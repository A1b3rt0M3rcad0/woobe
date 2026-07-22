from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from modules.evaluation.application.evidence_service import (
    EvidenceRichEvaluationApplicationService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation-evidence"])


@router.get("/evaluations/runs/{run_id}")
async def get_evaluation_run_evidence(
    project_id: UUID,
    run_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    service = EvidenceRichEvaluationApplicationService(
        request.app.state.session_factory
    )
    return {
        "success": True,
        "data": await service.get_run(project_id, run_id),
    }


__all__ = ["router"]
