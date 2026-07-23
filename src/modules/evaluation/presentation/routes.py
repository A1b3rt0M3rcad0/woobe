from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, Field

from modules.evaluation.application.governed_experience_service import (
    GovernedEvaluationExperienceService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class EvaluationCaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    message: str | None = Field(default=None, min_length=1)
    input_payload: dict[str, Any] | None = None
    initial_context: dict[str, Any] | None = None
    case_type: Literal["success", "refusal", "handled_error", "expected_failure"] = "success"
    expected_outcome: dict[str, Any] | None = None
    expected_contract: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["low", "normal", "high", "critical"] = "normal"
    weight: float = Field(default=1.0, gt=0, le=100)
    blocking: bool = False
    tags: list[str] = Field(default_factory=list, max_length=50)
    production_frequency: float | None = Field(default=None, ge=0, le=1)


class CreateDatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    change_description: str | None = Field(default=None, max_length=2000)
    cases: list[EvaluationCaseRequest] = Field(min_length=1, max_length=500)


class CreateDatasetVersionRequest(BaseModel):
    change_description: str = Field(min_length=3, max_length=2000)
    cases: list[EvaluationCaseRequest] = Field(min_length=1, max_length=500)


class CreateSuiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    target_type: Literal["agent", "network"]
    dataset_version_id: UUID
    judge_provider_model_id: UUID
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
            "maximum_cost_usd": None,
            "reasoning_policy": "provider_default",
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
    estimate_defaults: dict[str, Any] = Field(default_factory=lambda: {"volume": 10_000})


class CreateComposedSuiteVersionRequest(BaseModel):
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


class EvaluationTargetVariantRequest(BaseModel):
    type: Literal["model_override"]
    provider_model_id: UUID
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=128, le=32768)


class EvaluationTargetRequest(BaseModel):
    target_type: Literal["agent", "network"]
    source_type: Literal["draft", "staging", "release"]
    entity_id: UUID
    version_id: UUID | None = None
    variant: EvaluationTargetVariantRequest | None = None


class EvaluationRunRequest(BaseModel):
    suite_version_id: UUID
    repetitions: int = Field(default=3, ge=1, le=25)
    candidate: EvaluationTargetRequest
    baseline: EvaluationTargetRequest | None = None
    acknowledge_tool_side_effects: bool = False
    approved_high_risk_tool_ids: list[UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=255)


class RetryJudgmentsRequest(BaseModel):
    trial_ids: list[UUID] = Field(default_factory=list, max_length=5000)
    failure_codes: list[str] = Field(default_factory=list, max_length=20)


class CreateEstimateRequest(BaseModel):
    volume: int = Field(ge=1, le=1_000_000_000)
    volume_unit: Literal["runs_per_month", "sessions_per_month"] = "runs_per_month"


def _service(request: Request) -> GovernedEvaluationExperienceService:
    return GovernedEvaluationExperienceService(request.app.state.session_factory)


def _cases(values: list[EvaluationCaseRequest]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in values:
        data = item.model_dump(exclude_none=True)
        input_payload = dict(data.get("input_payload") or {})
        message = (
            input_payload.get("message")
            or input_payload.get("input")
            or input_payload.get("prompt")
            or data.get("message")
        )
        if isinstance(message, str) and message.strip():
            input_payload["message"] = message.strip()
            input_payload.pop("input", None)
            input_payload.pop("prompt", None)
        expected_contract = dict(data.get("expected_contract") or {})
        if isinstance(data.get("expected_outcome"), dict):
            expected_contract["expected_outcome"] = data["expected_outcome"]
        data["expected_contract"] = expected_contract
        data["input_payload"] = input_payload
        data.pop("message", None)
        data.pop("expected_outcome", None)
        normalized.append(data)
    return normalized


@router.post("/datasets", status_code=status.HTTP_201_CREATED)
async def create_dataset(project_id: UUID, payload: CreateDatasetRequest, request: Request):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_dataset(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        cases=_cases(payload.cases),
        change_description=payload.change_description,
        created_by=user_id,
    )
    return {"success": True, "data": data}


@router.get("/datasets")
async def list_datasets(
    project_id: UUID,
    request: Request,
    include_archived: bool = False,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_datasets_operational(
            project_id,
            include_archived=include_archived,
        ),
    }


@router.get("/datasets/{dataset_id}")
async def get_dataset(project_id: UUID, dataset_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).get_dataset(project_id, dataset_id)}


@router.post("/datasets/{dataset_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_dataset_version(
    project_id: UUID,
    dataset_id: UUID,
    payload: CreateDatasetVersionRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_dataset_version(
        project_id=project_id,
        dataset_id=dataset_id,
        cases=_cases(payload.cases),
        change_description=payload.change_description,
        created_by=user_id,
    )
    return {"success": True, "data": data}


@router.post("/datasets/{dataset_id}/archive")
async def archive_dataset(project_id: UUID, dataset_id: UUID, request: Request):
    user_id = require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).archive_dataset(project_id, dataset_id, user_id)}


@router.post("/datasets/{dataset_id}/restore")
async def restore_dataset(project_id: UUID, dataset_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).restore_dataset(project_id, dataset_id)}


@router.post("/suites", status_code=status.HTTP_201_CREATED)
async def create_suite(project_id: UUID, payload: CreateSuiteRequest, request: Request):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_suite(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        target_type=payload.target_type,
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


@router.get("/suites")
async def list_suites(
    project_id: UUID,
    request: Request,
    include_archived: bool = False,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_suites(
            project_id,
            include_archived=include_archived,
        ),
    }


@router.post("/suites/{suite_id}/versions/composed", status_code=status.HTTP_201_CREATED)
async def create_composed_suite_version(
    project_id: UUID,
    suite_id: UUID,
    payload: CreateComposedSuiteVersionRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_composed_suite_version(
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


@router.post("/suites/{suite_id}/archive")
async def archive_suite(project_id: UUID, suite_id: UUID, request: Request):
    user_id = require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).archive_suite(project_id, suite_id, user_id)}


@router.post("/suites/{suite_id}/restore")
async def restore_suite(project_id: UUID, suite_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).restore_suite(project_id, suite_id)}


@router.post("/runs/preview")
async def preview_run(project_id: UUID, payload: EvaluationRunRequest, request: Request):
    require_evaluation_user(request, project_id)
    data = await _service(request).preview_run(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        candidate=payload.candidate.model_dump(mode="json", exclude_none=True),
        baseline=payload.baseline.model_dump(mode="json", exclude_none=True) if payload.baseline else None,
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
    )
    return {"success": True, "data": data}


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(project_id: UUID, payload: EvaluationRunRequest, request: Request):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_run(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        candidate=payload.candidate.model_dump(mode="json", exclude_none=True),
        baseline=payload.baseline.model_dump(mode="json", exclude_none=True) if payload.baseline else None,
        requested_by=user_id,
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
        idempotency_key=payload.idempotency_key,
    )
    return {"success": True, "data": data}


@router.get("/runs/page")
async def list_runs_page(
    project_id: UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_runs_page(
            project_id,
            limit=limit,
            cursor=cursor,
        ),
    }


@router.get("/runs")
async def list_runs(
    project_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).list_runs(project_id, limit=limit)}


@router.get("/runs/{run_id}/progress")
async def get_run_progress(project_id: UUID, run_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).get_run_progress(project_id, run_id),
    }


@router.post("/runs/{run_id}/retry-judgments", status_code=status.HTTP_202_ACCEPTED)
async def retry_judgments(
    project_id: UUID,
    run_id: UUID,
    payload: RetryJudgmentsRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).retry_judgments(
            project_id=project_id,
            run_id=run_id,
            trial_ids=payload.trial_ids or None,
            failure_codes=payload.failure_codes or None,
        ),
    }


@router.get("/runs/{run_id}")
async def get_run(project_id: UUID, run_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).get_run(project_id, run_id)}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(project_id: UUID, run_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).cancel_run(project_id, run_id)}


@router.post("/runs/{run_id}/estimates", status_code=status.HTTP_201_CREATED)
async def create_estimate(
    project_id: UUID,
    run_id: UUID,
    payload: CreateEstimateRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_estimate(
        project_id=project_id,
        run_id=run_id,
        volume=payload.volume,
        volume_unit=payload.volume_unit,
        created_by=user_id,
    )
    return {"success": True, "data": data}


@router.get("/qualifications")
async def list_qualifications(
    project_id: UUID,
    request: Request,
    target_type: Literal["agent", "network"] | None = None,
    entity_id: UUID | None = None,
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_qualifications(
            project_id=project_id,
            target_type=target_type,
            entity_id=entity_id,
        ),
    }
