from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from modules.evaluation.application.complete_catalog_service import (
    CompleteEvaluationCatalogService,
)
from modules.evaluation.presentation.catalog_routes import CreatePairedComparisonRequest
from modules.evaluation.presentation.dependencies import require_evaluation_user
from shared.infra.errors import ConflictError

router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation-comparisons"])


@router.post("/comparisons/paired/preview")
async def preview_paired_comparison(
    project_id: UUID,
    payload: CreatePairedComparisonRequest,
    request: Request,
):
    require_evaluation_user(request, project_id)
    service = CompleteEvaluationCatalogService(request.app.state.session_factory)
    candidate = await service.preview_evaluation(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        target=payload.candidate.model_dump(mode="json", exclude_none=True),
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
        judge_provider_model_id=payload.judge_provider_model_id,
    )
    reference = await service.preview_evaluation(
        project_id=project_id,
        suite_version_id=payload.suite_version_id,
        repetitions=payload.repetitions,
        target=payload.reference.model_dump(mode="json", exclude_none=True),
        acknowledge_tool_side_effects=payload.acknowledge_tool_side_effects,
        approved_high_risk_tool_ids=payload.approved_high_risk_tool_ids,
        judge_provider_model_id=payload.judge_provider_model_id,
    )
    if candidate["target"]["snapshot_hash"] == reference["target"]["snapshot_hash"]:
        raise ConflictError(
            "Candidate and Reference resolve to the same immutable snapshot"
        )
    tools = {
        str(item["id"]): item
        for item in [
            *(candidate.get("preflight", {}).get("tools") or []),
            *(reference.get("preflight", {}).get("tools") or []),
        ]
    }
    data = {
        "mode": "paired_comparison",
        "candidate": candidate["target"],
        "reference": reference["target"],
        "case_count": candidate["case_count"],
        "repetitions": payload.repetitions,
        "target_run_count": candidate["target_run_count"] + reference["target_run_count"],
        "judge_call_count": candidate["judge_call_count"] + reference["judge_call_count"],
        "judge_provider_model_id": candidate.get("judge_provider_model_id"),
        "judge_preflight": candidate.get("judge_preflight"),
        "evaluation_protocol_hash": candidate["evaluation_protocol_hash"],
        "preflight": {
            "tools": list(tools.values()),
            "requires_acknowledgement": bool(
                candidate.get("preflight", {}).get("requires_acknowledgement")
                or reference.get("preflight", {}).get("requires_acknowledgement")
            ),
            "blocked_high_risk_tool_ids": sorted(
                {
                    *candidate.get("preflight", {}).get("blocked_high_risk_tool_ids", []),
                    *reference.get("preflight", {}).get("blocked_high_risk_tool_ids", []),
                }
            ),
        },
        "requires_confirmation": bool(
            candidate.get("requires_confirmation")
            or reference.get("requires_confirmation")
        ),
        "can_execute": bool(candidate.get("can_execute") and reference.get("can_execute")),
        "operations": {
            "evaluation_runs": 2,
            "comparisons": 1,
        },
    }
    return {"success": True, "data": data}


__all__ = ["router"]
