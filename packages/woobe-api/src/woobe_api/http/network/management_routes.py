from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from modules.network.entrypoint import (
    NetworkBoundaryService,
    build_network_service,
)
from shared.infra.errors import AuthorizationError
from shared.security.principal import (
    AuthenticatedPrincipal,
    ControlPlanePrincipal,
    ProjectApiPrincipal,
)


router = APIRouter(prefix="/network", tags=["network"])


class ActivateProductionRequest(BaseModel):
    project_id: UUID
    source_version_id: UUID
    expected_current_production_version_id: UUID | None = None
    change_description: str = Field(min_length=3, max_length=2000)


def _authorize_project(request: Request, project_id: UUID) -> UUID | None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return None
    if isinstance(principal, ControlPlanePrincipal):
        return None
    if isinstance(principal, AuthenticatedPrincipal):
        return principal.user_id
    raise AuthorizationError("Authentication required")


def _version_payload(version) -> dict:
    return {
        "id": str(version.id),
        "kind": version.kind,
        "version": version.version,
        "composition_hash": version.composition_hash,
        "definition": version.definition,
        "resolved_bindings": version.resolved_bindings,
        "created_at": version.created_at,
        "created_by": str(version.created_by) if version.created_by else None,
        "source_version_id": str(version.source_version_id)
        if version.source_version_id
        else None,
        "activation_kind": version.activation_kind,
        "change_description": version.change_description,
        **NetworkBoundaryService.version_extension_payload(version),
    }


def _activation_payload(activation) -> dict:
    return {
        "id": str(activation.id),
        "network_id": str(activation.network_id),
        "version_id": str(activation.version_id),
        "previous_version_id": str(activation.previous_version_id)
        if activation.previous_version_id
        else None,
        "activation_kind": activation.activation_kind,
        "change_description": activation.change_description,
        "created_by": str(activation.created_by) if activation.created_by else None,
        "created_at": activation.created_at,
    }


@router.get("/{network_id}/management/versions")
async def list_managed_network_versions(
    network_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    versions = await build_network_service().list_managed_versions(
        network_id=network_id,
        project_id=project_id,
    )
    return {"success": True, "data": [_version_payload(item) for item in versions]}


@router.get("/{network_id}/management/external-context-contract")
async def get_network_external_context_contract(
    network_id: UUID,
    project_id: UUID,
    environment: str,
    request: Request,
):
    _authorize_project(request, project_id)
    contract = await build_network_service().effective_external_context_contract(
        network_id=network_id,
        project_id=project_id,
        environment=environment,
    )
    return {"success": True, "data": contract}


@router.get("/{network_id}/management/activations")
async def list_network_production_activations(
    network_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    activations = await build_network_service().list_production_activations(
        network_id=network_id,
        project_id=project_id,
    )
    return {
        "success": True,
        "data": [_activation_payload(item) for item in activations],
    }


@router.get("/executions/{execution_id}/snapshot")
async def get_network_execution_snapshot(
    execution_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    snapshot = await build_network_service().execution_snapshot(
        execution_id=execution_id,
        project_id=project_id,
    )
    return {"success": True, "data": snapshot}


@router.post(
    "/{network_id}/production/activations",
    status_code=status.HTTP_201_CREATED,
)
async def activate_network_production(
    network_id: UUID,
    payload: ActivateProductionRequest,
    request: Request,
):
    created_by = _authorize_project(request, payload.project_id)
    description = payload.change_description.strip()
    source, activation = await build_network_service().activate_production(
        network_id=network_id,
        project_id=payload.project_id,
        source_version_id=payload.source_version_id,
        expected_current_production_version_id=(
            payload.expected_current_production_version_id
        ),
        change_description=description,
        created_by=created_by,
    )

    return {
        "success": True,
        "data": {
            "version": _version_payload(source),
            "activation": _activation_payload(activation),
        },
    }
