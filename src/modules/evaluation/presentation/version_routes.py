from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from modules.evaluation.application.version_service import (
    EvaluationVersionApplicationService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user


router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class CreateSuiteVersionRequest(BaseModel):
    dataset_version_id: UUID
    judge_provider_model_id: UUID
    judge_config: dict[str, Any] = Field(
        default_factory=lambda: {
            "temperature": 0,
            "max_tokens": 1600,
            "timeout_seconds": 90,
            "maximum_cost_usd": None,
        }
    )
    rubric: dict[str, Any] = Field(default_factory=dict)
    deterministic_checks: dict[str, Any] = Field(default_factory=dict)
    acceptance_policy: dict[str, Any] = Field(
        default_factory=lambda: {
            "minimum_score": 70,
            "minimum_pass_rate": 80,
            "minimum_paired_n": 3,
            "maximum_score_regression": 0,
            "maximum_latency_regression_percent": None,
            "maximum_cost_regression_percent": None,
        }
    )
    repetition_policy: dict[str, Any] = Field(
        default_factory=lambda: {"default_repetitions": 3, "maximum_repetitions": 25}
    )
    estimate_defaults: dict[str, Any] = Field(
        default_factory=lambda: {"volume": 10_000}
    )


@router.post("/suites/{suite_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_suite_version(
    project_id: UUID,
    suite_id: UUID,
    payload: CreateSuiteVersionRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    service = EvaluationVersionApplicationService(request.app.state.session_factory)
    data = await service.create_suite_version(
        project_id=project_id,
        suite_id=suite_id,
        dataset_version_id=payload.dataset_version_id,
        judge_provider_model_id=payload.judge_provider_model_id,
        judge_config=payload.judge_config,
        rubric=payload.rubric,
        deterministic_checks=payload.deterministic_checks,
        acceptance_policy=payload.acceptance_policy,
        repetition_policy=payload.repetition_policy,
        estimate_defaults=payload.estimate_defaults,
        created_by=user_id,
    )
    return {"success": True, "data": data}
