from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from modules.evaluation.application.revision_comparison_service import (
    RevisionComparisonCatalogService,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation-catalog"])


class CatalogTargetRequest(BaseModel):
    target_type: Literal["agent", "network"]
    source_type: Literal["draft", "staging", "release"]
    entity_id: UUID
    version_id: UUID | None = None


class EvaluationPreviewRequest(BaseModel):
    suite_version_id: UUID
    repetitions: int = Field(default=3, ge=1, le=25)
    target: CatalogTargetRequest
    acknowledge_tool_side_effects: bool = False
    approved_high_risk_tool_ids: list[UUID] = Field(default_factory=list, max_length=100)


class CreateEvaluationRunRequest(EvaluationPreviewRequest):
    idempotency_key: str = Field(min_length=8, max_length=255)


class ComparisonPreviewRequest(BaseModel):
    candidate_run_id: UUID
    reference_run_id: UUID


class CreateComparisonFromRunsRequest(ComparisonPreviewRequest):
    candidate_evidence_revision: int | None = Field(default=None, ge=1)
    reference_evidence_revision: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=255)


class CreatePairedComparisonRequest(BaseModel):
    suite_version_id: UUID
    repetitions: int = Field(default=3, ge=1, le=25)
    candidate: CatalogTargetRequest
    reference: CatalogTargetRequest
    acknowledge_tool_side_effects: bool = False
    approved_high_risk_tool_ids: list[UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=220)


class ComparisonDecisionRequest(BaseModel):
    decision: Literal["select_candidate", "keep_reference", "no_preference"]
    decision_basis: Literal["evidence", "manual_override"] = "evidence"
    note: str | None = Field(default=None, max_length=4000)


def _service(request: Request) -> RevisionComparisonCatalogService:
    return RevisionComparisonCatalogService(request.app.state.session_factory)


@router.post("/evaluations/preview")
async def preview_evaluation(
    project_id: UUID,
    payload: EvaluationPreviewRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).preview_evaluation(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        target=payload.target.model_dump(mode="json", exclude_none=True),
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
    )
    return {"success": True, "data": data}


@router.post("/evaluations/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_evaluation_run(
    project_id: UUID,
    payload: CreateEvaluationRunRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_evaluation_run(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        target=payload.target.model_dump(mode="json", exclude_none=True),
        requested_by=user_id,
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
        idempotency_key=payload.idempotency_key,
    )
    return {"success": True, "data": data}


@router.get("/evaluations")
async def list_evaluations(
    project_id: UUID,
    request: Request,
    target_type: Literal["agent", "network"] | None = None,
    entity_id: UUID | None = None,
    suite_version_id: UUID | None = None,
    include_archived: bool = False,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).list_evaluations(
        project_id=project_id,
        target_type=target_type,
        entity_id=entity_id,
        suite_version_id=suite_version_id,
        include_archived=include_archived,
    )
    return {"success": True, "data": data}


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation(
    project_id: UUID,
    evaluation_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).get_evaluation(
        project_id=project_id,
        evaluation_id=evaluation_id,
    )
    return {"success": True, "data": data}


@router.post("/evaluations/{evaluation_id}/archive")
async def archive_evaluation(
    project_id: UUID,
    evaluation_id: UUID,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).archive_evaluation(
        project_id=project_id,
        evaluation_id=evaluation_id,
        archived_by=user_id,
    )
    return {"success": True, "data": data}


@router.post("/evaluations/{evaluation_id}/restore")
async def restore_evaluation(
    project_id: UUID,
    evaluation_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).restore_evaluation(
        project_id=project_id,
        evaluation_id=evaluation_id,
    )
    return {"success": True, "data": data}


@router.post("/comparisons/preview")
async def preview_comparison(
    project_id: UUID,
    payload: ComparisonPreviewRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).preview_comparison(
        project_id=project_id,
        candidate_run_id=payload.candidate_run_id,
        reference_run_id=payload.reference_run_id,
    )
    return {"success": True, "data": data}


@router.post("/comparisons/from-runs", status_code=status.HTTP_201_CREATED)
async def create_comparison_from_runs(
    project_id: UUID,
    payload: CreateComparisonFromRunsRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_comparison_from_runs(
        project_id=project_id,
        candidate_run_id=payload.candidate_run_id,
        reference_run_id=payload.reference_run_id,
        candidate_revision=payload.candidate_evidence_revision,
        reference_revision=payload.reference_evidence_revision,
        requested_by=user_id,
        idempotency_key=payload.idempotency_key,
    )
    return {"success": True, "data": data}


@router.post("/comparisons/paired", status_code=status.HTTP_202_ACCEPTED)
async def create_paired_comparison(
    project_id: UUID,
    payload: CreatePairedComparisonRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_paired_comparison(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        candidate=payload.candidate.model_dump(mode="json", exclude_none=True),
        reference=payload.reference.model_dump(mode="json", exclude_none=True),
        requested_by=user_id,
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
        idempotency_key=payload.idempotency_key,
    )
    return {"success": True, "data": data}


@router.get("/comparisons")
async def list_comparisons(
    project_id: UUID,
    request: Request,
    entity_id: UUID | None = None,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).list_comparisons(
        project_id=project_id,
        entity_id=entity_id,
    )
    return {"success": True, "data": data}


@router.get("/comparisons/{comparison_id}")
async def get_comparison(
    project_id: UUID,
    comparison_id: UUID,
    request: Request,
):
    require_evaluation_user(request, project_id)
    data = await _service(request).get_comparison(
        project_id=project_id,
        comparison_id=comparison_id,
    )
    return {"success": True, "data": data}


@router.post("/comparisons/{comparison_id}/decision")
async def create_comparison_decision(
    project_id: UUID,
    comparison_id: UUID,
    payload: ComparisonDecisionRequest,
    request: Request,
):
    user_id = require_evaluation_user(request, project_id)
    data = await _service(request).create_comparison_decision(
        project_id=project_id,
        comparison_id=comparison_id,
        decision=payload.decision,
        decision_basis=payload.decision_basis,
        note=payload.note,
        decided_by=user_id,
    )
    return {"success": True, "data": data}


__all__ = ["router"]
