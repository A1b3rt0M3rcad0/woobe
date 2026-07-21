from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.infra.database.models import (
    EvaluationDatasetVersionModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/evaluation/projects/{project_id}", tags=["evaluation"])


class CreateSuiteVersionRequest(BaseModel):
    dataset_version_id: UUID
    judge_provider_model_id: UUID
    judge_config: dict[str, Any] = Field(default_factory=lambda: {"temperature": 0, "max_tokens": 1600})
    rubric: dict[str, Any] = Field(default_factory=dict)
    deterministic_checks: dict[str, Any] = Field(default_factory=dict)
    acceptance_policy: dict[str, Any] = Field(default_factory=lambda: {"minimum_score": 70, "minimum_pass_rate": 80})
    repetition_policy: dict[str, Any] = Field(default_factory=lambda: {"default_repetitions": 3, "maximum_repetitions": 25})
    estimate_defaults: dict[str, Any] = Field(default_factory=lambda: {"volume": 10_000})


def _authorize_project(request: Request, project_id: UUID) -> UUID | None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return None
    if isinstance(principal, AuthenticatedPrincipal):
        return principal.user_id
    raise AuthorizationError("Authentication required")


@router.post("/suites/{suite_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_suite_version(
    project_id: UUID,
    suite_id: UUID,
    payload: CreateSuiteVersionRequest,
    request: Request,
):
    user_id = _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session, session.begin():
        suite = await session.get(EvaluationSuiteModel, suite_id, with_for_update=True)
        if suite is None or suite.project_id != project_id:
            raise NotFoundError("Evaluation Suite not found")
        dataset_version = await session.get(EvaluationDatasetVersionModel, payload.dataset_version_id)
        if dataset_version is None or dataset_version.project_id != project_id:
            raise NotFoundError("Evaluation Dataset version not found")
        provider_model = await session.get(ProviderModelModel, payload.judge_provider_model_id)
        if provider_model is None or provider_model.project_id != project_id or provider_model.status != "active":
            raise NotFoundError("Evaluator Provider Model not found")
        count = int(
            await session.scalar(
                select(func.count(EvaluationSuiteVersionModel.id)).where(
                    EvaluationSuiteVersionModel.suite_id == suite.id
                )
            )
            or 0
        )
        snapshot = {
            "dataset_version_id": str(payload.dataset_version_id),
            "judge_provider_model_id": str(payload.judge_provider_model_id),
            "judge_config": payload.judge_config,
            "rubric": payload.rubric,
            "deterministic_checks": payload.deterministic_checks,
            "acceptance_policy": payload.acceptance_policy,
            "repetition_policy": payload.repetition_policy,
            "estimate_defaults": payload.estimate_defaults,
        }
        version = EvaluationSuiteVersionModel(
            suite_id=suite.id,
            project_id=project_id,
            version=f"v{count + 1}",
            dataset_version_id=payload.dataset_version_id,
            judge_provider_model_id=payload.judge_provider_model_id,
            judge_config=payload.judge_config,
            rubric=payload.rubric,
            deterministic_checks=payload.deterministic_checks,
            acceptance_policy=payload.acceptance_policy,
            repetition_policy=payload.repetition_policy,
            estimate_defaults=payload.estimate_defaults,
            suite_hash=canonical_hash(snapshot),
            created_by=user_id,
        )
        session.add(version)
        await session.flush()
        suite.current_version_id = version.id
        return {
            "success": True,
            "data": {
                "id": str(suite.id),
                "project_id": str(project_id),
                "name": suite.name,
                "description": suite.description,
                "target_type": suite.target_type,
                "status": suite.status,
                "current_version_id": str(version.id),
                "current_version": version.version,
                "dataset_version_id": str(version.dataset_version_id),
                "judge_provider_model_id": str(version.judge_provider_model_id),
                "judge_config": version.judge_config,
                "rubric": version.rubric,
                "acceptance_policy": version.acceptance_policy,
                "repetition_policy": version.repetition_policy,
                "estimate_defaults": version.estimate_defaults,
                "suite_hash": version.suite_hash,
                "created_at": suite.created_at,
                "updated_at": suite.updated_at,
            },
        }
