from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from modules.network.entrypoint import build_network_service
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/network", tags=["network"])


def _authorize_project(request: Request, project_id: UUID) -> None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")


@router.get("/executions/{execution_id}/diagnostics")
async def get_network_run_diagnostics(
    execution_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    diagnostics = await build_network_service().diagnostics(
        execution_id=execution_id,
        project_id=project_id,
    )
    if diagnostics is None:
        raise NotFoundError("Network execution not found")
    return {"success": True, "data": diagnostics}
