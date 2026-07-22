from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.presentation.dependencies import require_evaluation_user
from shared.infra.errors import ConflictError

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class EvaluationDecisionRequest(BaseModel):
    target_id: UUID | None = None
    decision: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=4000)


@router.post("/runs/{run_id}/decision")
async def decide_evaluation_target(
    project_id: UUID,
    run_id: UUID,
    payload: EvaluationDecisionRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    service = EvaluationExperienceService(request.app.state.session_factory)
    run = await service.get_run(project_id, run_id)
    if run.get("mode") == "model_experiment":
        raise ConflictError(
            "Legacy Model Experiments cannot receive an operational target decision"
        )
    data = await service.create_decision(
        project_id=project_id,
        run_id=run_id,
        target_id=payload.target_id,
        decision=payload.decision,
        note=payload.note,
        decided_by=user_id,
    )
    return {"success": True, "data": data}


__all__ = ["router"]
