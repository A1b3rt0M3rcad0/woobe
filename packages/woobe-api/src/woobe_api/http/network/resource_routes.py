from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field, model_validator

from modules.network.entrypoint import build_network_service
from shared.infra.errors import AuthorizationError
from shared.security.principal import (
    AuthenticatedPrincipal,
    ControlPlanePrincipal,
    ProjectApiPrincipal,
)


router = APIRouter(prefix="/network/projects", tags=["network"])


class CreateNetworkRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def normalize(self) -> "CreateNetworkRequest":
        self.name = self.name.strip()
        self.description = self.description.strip()
        if not self.name:
            raise ValueError("Network name cannot be blank")
        return self


class UpdateNetworkMetadataRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def normalize(self) -> "UpdateNetworkMetadataRequest":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Network name cannot be blank")
        if self.description is not None:
            self.description = self.description.strip()
        if self.name is None and self.description is None:
            raise ValueError("At least one Network metadata field is required")
        return self


def _authorize_project(request: Request, project_id: UUID) -> None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return
    if isinstance(principal, ControlPlanePrincipal):
        return
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")


def _agent_count(network) -> int:
    definition = network.draft_definition or {}
    nodes = definition.get("nodes") if isinstance(definition, dict) else None
    return len(nodes) if isinstance(nodes, list) else 0


def network_payload(network) -> dict:
    return {
        "id": str(network.id),
        "project_id": str(network.project_id),
        "name": network.name,
        "description": network.description,
        "draft_definition": network.draft_definition,
        "draft_revision": network.draft_revision,
        "staging_version_id": str(network.staging_version_id)
        if network.staging_version_id
        else None,
        "production_version_id": str(network.production_version_id)
        if network.production_version_id
        else None,
        "agent_count": _agent_count(network),
        "created_at": network.created_at,
        "updated_at": network.updated_at,
    }


@router.get("/{project_id}/networks")
async def list_project_networks(project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    networks = await build_network_service().list_project_networks(project_id)
    return {"success": True, "data": [network_payload(item) for item in networks]}


@router.post("/{project_id}/networks", status_code=status.HTTP_201_CREATED)
async def create_project_network(
    project_id: UUID,
    payload: CreateNetworkRequest,
    request: Request,
):
    _authorize_project(request, project_id)
    network = await build_network_service().create_project_network(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
    )
    return {"success": True, "data": network_payload(network)}


@router.delete("/{project_id}/networks/{network_id}")
async def delete_project_network(
    project_id: UUID,
    network_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    await build_network_service().delete_project_network(
        project_id=project_id,
        network_id=network_id,
    )
    return {"success": True, "data": None}


@router.get("/{project_id}/networks/{network_id}")
async def get_project_network(project_id: UUID, network_id: UUID, request: Request):
    _authorize_project(request, project_id)
    network = await build_network_service().get_project_network(
        project_id=project_id,
        network_id=network_id,
    )
    return {"success": True, "data": network_payload(network)}


@router.patch("/{project_id}/networks/{network_id}")
async def update_project_network_metadata(
    project_id: UUID,
    network_id: UUID,
    payload: UpdateNetworkMetadataRequest,
    request: Request,
):
    _authorize_project(request, project_id)
    network = await build_network_service().update_project_network_metadata(
        project_id=project_id,
        network_id=network_id,
        name=payload.name,
        description=payload.description,
    )
    return {"success": True, "data": network_payload(network)}
