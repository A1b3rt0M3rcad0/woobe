from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field, model_validator

from modules.evaluation.application.governed_experience_service import (
    GovernedEvaluationExperienceService,
)
from modules.evaluation.application.session_authoring import (
    SessionAwareEvaluationSuiteAuthoringService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation-authoring"])


class AuthoringTargetRequest(BaseModel):
    target_type: Literal["agent", "network"]
    source_type: Literal["draft", "staging", "release"]
    entity_id: UUID
    version_id: UUID | None = None


class ContextPreviewRequest(BaseModel):
    target: AuthoringTargetRequest
    generator_provider_model_id: UUID
    objective: str = Field(min_length=10, max_length=5000)
    case_count: int = Field(default=20, ge=5, le=50)
    maximum_input_tokens: int = Field(default=16_000, ge=2_000, le=64_000)


class GenerateSuiteDraftRequest(ContextPreviewRequest):
    coverage: dict[str, int] = Field(default_factory=dict)
    error_case_ratio: float = Field(default=0.3, ge=0, le=0.8)
    language: str = Field(default="pt-BR", min_length=2, max_length=32)
    maximum_cost_usd: float | None = Field(default=None, gt=0, le=100)
    test_structure: Literal["single_turn", "session", "mixed"] = "single_turn"
    minimum_session_turns: int = Field(default=2, ge=2, le=10)
    maximum_session_turns: int = Field(default=5, ge=2, le=20)

    @model_validator(mode="after")
    def validate_session_turn_range(self):
        if self.maximum_session_turns < self.minimum_session_turns:
            raise ValueError(
                "maximum_session_turns must be greater than or equal to minimum_session_turns"
            )
        return self


class ResumeSuiteDraftRequest(BaseModel):
    provider_model_id: UUID | None = None
    strategy: Literal[
        "retry_failed_and_missing",
        "repair_tool_references",
        "retry_provider_call",
        "continue_with_new_model",
        "retry_with_larger_output_budget",
    ] = "retry_failed_and_missing"


class ValidateSuiteDraftRequest(BaseModel):
    draft: dict[str, Any]
    reference_target: AuthoringTargetRequest | None = None


class CreateComposedSuiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    target_type: Literal["agent", "network"]
    judge_provider_model_id: UUID
    draft: dict[str, Any]
    judge_config: dict[str, Any] = Field(
        default_factory=lambda: {
            "temperature": 0,
            "output_budget_policy": "fixed",
            "max_tokens": 1200,
            "maximum_retry_tokens": 2048,
            "platform_output_cap": 4096,
            "attempts": 3,
            "timeout_seconds": 90,
            "maximum_input_tokens": 8000,
            "reasoning_policy": "provider_default",
        }
    )
    rubric: dict[str, Any] = Field(
        default_factory=lambda: {
            "criteria": [
                "Correctness",
                "Relevance",
                "Completeness",
                "Expected behavior",
            ],
            "judge_weight": 4,
        }
    )
    deterministic_checks: dict[str, Any] = Field(default_factory=lambda: {"enabled": True})
    acceptance_policy: dict[str, Any] = Field(
        default_factory=lambda: {
            "minimum_score": 70,
            "minimum_pass_rate": 80,
            "minimum_paired_n": 3,
            "maximum_score_regression": 0,
        }
    )
    repetition_policy: dict[str, Any] = Field(
        default_factory=lambda: {"default_repetitions": 3, "maximum_repetitions": 25}
    )
    estimate_defaults: dict[str, Any] = Field(default_factory=lambda: {"volume": 10_000})
    authoring_source: Literal["manual", "json_import", "ai_generated"] = "manual"
    source_snapshot_hash: str | None = Field(default=None, max_length=64)
    source_context_hash: str | None = Field(default=None, max_length=64)
    authoring_metadata: dict[str, Any] = Field(default_factory=dict)


def _service(request: Request) -> SessionAwareEvaluationSuiteAuthoringService:
    return SessionAwareEvaluationSuiteAuthoringService(request.app.state.session_factory)


def _governed_service(request: Request) -> GovernedEvaluationExperienceService:
    return GovernedEvaluationExperienceService(request.app.state.session_factory)


@router.post("/suite-authoring/context-preview")
async def preview_authoring_context(
    project_id: UUID,
    payload: ContextPreviewRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).preview_context(
        project_id=project_id,
        target=payload.target.model_dump(mode="json", exclude_none=True),
        generator_provider_model_id=payload.generator_provider_model_id,
        objective=payload.objective,
        case_count=payload.case_count,
        maximum_input_tokens=payload.maximum_input_tokens,
    )
    return {"success": True, "data": data}


@router.post("/suite-authoring/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_suite_draft(
    project_id: UUID,
    payload: GenerateSuiteDraftRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).generate_draft(
        project_id=project_id,
        target=payload.target.model_dump(mode="json", exclude_none=True),
        generator_provider_model_id=payload.generator_provider_model_id,
        objective=payload.objective,
        case_count=payload.case_count,
        coverage=payload.coverage,
        error_case_ratio=payload.error_case_ratio,
        language=payload.language,
        maximum_input_tokens=payload.maximum_input_tokens,
        maximum_cost_usd=payload.maximum_cost_usd,
        test_structure=payload.test_structure,
        minimum_session_turns=payload.minimum_session_turns,
        maximum_session_turns=payload.maximum_session_turns,
        created_by=user_id,
    )
    return {"success": True, "data": data}


@router.get("/suite-authoring/calls/{call_id}")
async def get_suite_authoring_call(
    project_id: UUID,
    call_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).get_authoring_call(project_id, call_id),
    }


@router.post("/suite-authoring/calls/{call_id}/cancel")
async def cancel_suite_authoring_call(
    project_id: UUID,
    call_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).cancel_authoring_call(project_id, call_id),
    }


@router.post("/suite-authoring/calls/{call_id}/retry")
async def retry_suite_authoring_call(
    project_id: UUID,
    call_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).retry_authoring_call(project_id, call_id),
    }


@router.post("/suite-authoring/calls/{call_id}/resume")
async def resume_suite_authoring_call(
    project_id: UUID,
    call_id: UUID,
    payload: ResumeSuiteDraftRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).resume_authoring_call(
            project_id=project_id,
            call_id=call_id,
            provider_model_id=payload.provider_model_id,
            strategy=payload.strategy,
        ),
    }


@router.post("/suite-authoring/validate")
async def validate_suite_draft(
    project_id: UUID,
    payload: ValidateSuiteDraftRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).validate_draft(
        payload.draft,
        project_id=project_id,
        reference_target=(
            payload.reference_target.model_dump(mode="json", exclude_none=True)
            if payload.reference_target
            else None
        ),
    )
    return {"success": True, "data": data}


@router.post("/suites/composed", status_code=status.HTTP_201_CREATED)
async def create_composed_suite(
    project_id: UUID,
    payload: CreateComposedSuiteRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    governed_config = await _governed_service(request)._govern_judge_config(
        project_id=project_id,
        judge_provider_model_id=payload.judge_provider_model_id,
        judge_config=payload.judge_config,
    )
    data = await _service(request).create_composed_suite(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        target_type=payload.target_type,
        judge_provider_model_id=payload.judge_provider_model_id,
        cases_payload=payload.draft,
        judge_config=governed_config,
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
