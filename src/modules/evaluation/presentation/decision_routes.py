from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.presentation.dependencies import require_evaluation_user
from shared.infra.errors import ConflictError, ValidationError

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class EvaluationDecisionRequest(BaseModel):
    target_id: UUID | None = None
    decision: Literal["accepted", "rejected"]
    decision_basis: Literal["evidence", "manual_override"] = "evidence"
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
    if run.get("status") not in {"completed", "partially_completed"}:
        raise ConflictError(
            "Only a completed Evaluation with persisted evidence can receive a decision"
        )
    assessment = str(run.get("assessment_status") or "inconclusive")
    conclusive = assessment in {"meets_policy", "below_policy"}
    normalized_note = payload.note.strip() if payload.note and payload.note.strip() else None
    if not conclusive and payload.decision_basis != "manual_override":
        raise ConflictError(
            "Inconclusive evidence cannot receive a normal decision. Use a manual override with justification."
        )
    if payload.decision_basis == "manual_override" and not normalized_note:
        raise ValidationError("Manual override requires a decision note")

    data = await service.create_decision(
        project_id=project_id,
        run_id=run_id,
        target_id=payload.target_id,
        decision=payload.decision,
        note=normalized_note,
        decided_by=user_id,
    )
    async with request.app.state.session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE evaluation.target_decisions "
                "SET decision_basis = :basis "
                "WHERE id = :decision_id AND project_id = :project_id"
            ),
            {
                "basis": payload.decision_basis,
                "decision_id": UUID(str(data["id"])),
                "project_id": project_id,
            },
        )
    data["decision_basis"] = payload.decision_basis
    return {"success": True, "data": data}


__all__ = ["router"]
