from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from modules.core.infra.database.models import ProjectModel
from modules.network.infra.database.models import NetworkModel
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


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
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")


def _agent_count(network: NetworkModel) -> int:
    definition = network.draft_definition or {}
    nodes = definition.get("nodes") if isinstance(definition, dict) else None
    return len(nodes) if isinstance(nodes, list) else 0


def network_payload(network: NetworkModel) -> dict:
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


async def _get_for_project(session, project_id: UUID, network_id: UUID) -> NetworkModel:
    network = await session.scalar(
        select(NetworkModel).where(
            NetworkModel.id == network_id,
            NetworkModel.project_id == project_id,
        )
    )
    if network is None:
        raise NotFoundError("Network not found")
    return network


@router.get("/{project_id}/networks")
async def list_project_networks(project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        project_exists = await session.scalar(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )
        if project_exists is None:
            raise NotFoundError("Project not found")
        networks = list(
            (
                await session.scalars(
                    select(NetworkModel)
                    .where(NetworkModel.project_id == project_id)
                    .order_by(NetworkModel.updated_at.desc(), NetworkModel.created_at.desc())
                )
            ).all()
        )
    return {"success": True, "data": [network_payload(item) for item in networks]}


@router.post("/{project_id}/networks", status_code=status.HTTP_201_CREATED)
async def create_project_network(
    project_id: UUID,
    payload: CreateNetworkRequest,
    request: Request,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session, session.begin():
        project_exists = await session.scalar(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )
        if project_exists is None:
            raise NotFoundError("Project not found")
        duplicate = await session.scalar(
            select(NetworkModel.id).where(
                NetworkModel.project_id == project_id,
                func.lower(func.btrim(NetworkModel.name)) == payload.name.lower(),
            )
        )
        if duplicate is not None:
            raise ConflictError("A Network with this name already exists in the Project")
        network = NetworkModel(
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            draft_definition={},
            draft_revision=0,
            staging_version_id=None,
            production_version_id=None,
        )
        session.add(network)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A Network with this name already exists in the Project"
            ) from exc
    return {"success": True, "data": network_payload(network)}


@router.get("/{project_id}/networks/{network_id}")
async def get_project_network(project_id: UUID, network_id: UUID, request: Request):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        network = await _get_for_project(session, project_id, network_id)
    return {"success": True, "data": network_payload(network)}


@router.patch("/{project_id}/networks/{network_id}")
async def update_project_network_metadata(
    project_id: UUID,
    network_id: UUID,
    payload: UpdateNetworkMetadataRequest,
    request: Request,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session, session.begin():
        network = await session.scalar(
            select(NetworkModel)
            .where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
            )
            .with_for_update()
        )
        if network is None:
            raise NotFoundError("Network not found")
        if payload.name is not None:
            duplicate = await session.scalar(
                select(NetworkModel.id).where(
                    NetworkModel.project_id == project_id,
                    NetworkModel.id != network_id,
                    func.lower(func.btrim(NetworkModel.name)) == payload.name.lower(),
                )
            )
            if duplicate is not None:
                raise ConflictError(
                    "A Network with this name already exists in the Project"
                )
            network.name = payload.name
        if payload.description is not None:
            network.description = payload.description
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A Network with this name already exists in the Project"
            ) from exc
    return {"success": True, "data": network_payload(network)}
