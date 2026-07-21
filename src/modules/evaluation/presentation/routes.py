from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, Field

from modules.evaluation.application.hardened_service import (
    HardenedEvaluationApplicationService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class EvaluationCaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    message: str | None = Field(default=None, min_length=1)
    input_payload: dict[str, Any] | None = None
    initial_context: dict[str, Any] | None = None
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


class EvaluationTargetRequest(BaseModel):
    target_type: Literal["agent", "network"]
    source_type: Literal["draft", "staging", "release"]
    entity_id: UUID
    version_id: UUID | None = None


class EvaluationRunRequest(BaseModel):
    suite_version_id: UUID
    repetitions: int = Field(default=3, ge=1, le=25)
    candidate: EvaluationTargetRequest
    baseline: EvaluationTargetRequest | None = None
    acknowledge_tool_side_effects: bool = False
    approved_high_risk_tool_ids: list[UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=255)


def _service(request: Request) -> HardenedEvaluationApplicationService:
    return HardenedEvaluationApplicationService(request.app.state.session_factory)


def _cases(values: list[EvaluationCaseRequest]) -> list[dict[str, Any]]:
    return [item.model_dump(exclude_none=True) for item in values]


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
async def list_datasets(project_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).list_datasets(project_id)}


@router.get("/datasets/{dataset_id}")
async def get_dataset(project_id: UUID, dataset_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).get_dataset(project_id, dataset_id),
    }


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
async def list_suites(project_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).list_suites(project_id)}


@router.post("/runs/preview")
async def preview_run(project_id: UUID, payload: EvaluationRunRequest, request: Request):
    require_evaluation_user(request, project_id)
    data = await _service(request).preview_run(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        candidate=payload.candidate.model_dump(mode="json"),
        baseline=payload.baseline.model_dump(mode="json") if payload.baseline else None,
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
        candidate=payload.candidate.model_dump(mode="json"),
        baseline=payload.baseline.model_dump(mode="json") if payload.baseline else None,
        requested_by=user_id,
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
        idempotency_key=payload.idempotency_key,
    )
    return {"success": True, "data": data}


@router.get("/runs")
async def list_runs(
    project_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
):
    require_evaluation_user(request, project_id)
    return {
        "success": True,
        "data": await _service(request).list_runs(project_id, limit=limit),
    }


@router.get("/runs/{run_id}")
async def get_run(project_id: UUID, run_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).get_run(project_id, run_id)}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(project_id: UUID, run_id: UUID, request: Request):
    require_evaluation_user(request, project_id)
    return {"success": True, "data": await _service(request).cancel_run(project_id, run_id)}


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
