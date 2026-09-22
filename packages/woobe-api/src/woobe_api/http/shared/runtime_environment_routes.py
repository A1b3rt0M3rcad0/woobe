from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from shared.infra.errors import AuthorizationError, ValidationError
from shared.runtime_environment import (
    build_runtime_environment_service,
    runtime_states_payload,
)
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal

router = APIRouter(tags=["runtime environments"])


class RuntimeEnvironmentUpdateRequest(BaseModel):
    project_id: UUID
    enabled: bool | None = None
    external_context_values: dict[str, object] | None = None


def _authorize_project(request: Request, project_id: UUID, *, write: bool) -> UUID | None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, AuthenticatedPrincipal):
        return principal.user_id
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        if write:
            raise AuthorizationError("Runtime keys cannot change runtime environment state")
        return None
    raise AuthorizationError("Authentication required")


async def _list_states(
    request: Request,
    *,
    target_type: str,
    target_id: UUID,
    project_id: UUID,
):
    _authorize_project(request, project_id, write=False)
    states = await build_runtime_environment_service().list_states(
        target_type=target_type,  # type: ignore[arg-type]
        target_id=target_id,
        project_id=project_id,
    )
    return {"success": True, "data": runtime_states_payload(states)}


async def _update_state(
    request: Request,
    *,
    target_type: str,
    target_id: UUID,
    environment: str,
    payload: RuntimeEnvironmentUpdateRequest,
):
    user_id = _authorize_project(request, payload.project_id, write=True)
    if payload.enabled is None and payload.external_context_values is None:
        raise ValidationError("Runtime environment update requires enabled or external_context_values")

    service = build_runtime_environment_service()
    state = None
    if payload.enabled is not None:
        state = await service.set_enabled(
            target_type=target_type,  # type: ignore[arg-type]
            target_id=target_id,
            project_id=payload.project_id,
            environment=environment,
            enabled=payload.enabled,
            updated_by=user_id,
        )
    if payload.external_context_values is not None:
        state = await service.set_external_context_values(
            target_type=target_type,  # type: ignore[arg-type]
            target_id=target_id,
            project_id=payload.project_id,
            environment=environment,
            values=payload.external_context_values,
            updated_by=user_id,
        )
    assert state is not None
    return {"success": True, "data": state.to_dict()}


@router.get("/ai/agents/{agent_id}/runtime-environments")
async def list_agent_runtime_environments(
    agent_id: UUID,
    project_id: UUID,
    request: Request,
):
    return await _list_states(
        request,
        target_type="agent",
        target_id=agent_id,
        project_id=project_id,
    )


@router.patch("/ai/agents/{agent_id}/runtime-environments/{environment}")
async def update_agent_runtime_environment(
    agent_id: UUID,
    environment: str,
    payload: RuntimeEnvironmentUpdateRequest,
    request: Request,
):
    return await _update_state(
        request,
        target_type="agent",
        target_id=agent_id,
        environment=environment,
        payload=payload,
    )


@router.get("/network/{network_id}/runtime-environments")
async def list_network_runtime_environments(
    network_id: UUID,
    project_id: UUID,
    request: Request,
):
    return await _list_states(
        request,
        target_type="network",
        target_id=network_id,
        project_id=project_id,
    )


@router.patch("/network/{network_id}/runtime-environments/{environment}")
async def update_network_runtime_environment(
    network_id: UUID,
    environment: str,
    payload: RuntimeEnvironmentUpdateRequest,
    request: Request,
):
    return await _update_state(
        request,
        target_type="network",
        target_id=network_id,
        environment=environment,
        payload=payload,
    )
