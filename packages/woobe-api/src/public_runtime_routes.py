from uuid import UUID

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from modules.agent.entrypoint import public_run_composer, public_stream_composer
from modules.agent.presentation.http.run_routes import (
    active_agent_run,
    attach_agent_run,
    cancel_agent_run,
)
from modules.network.entrypoint import (
    active_network_run_composer,
    attach_network_run_composer,
    cancel_runtime_network_execution_composer,
)
from modules.network.presentation.public_runtime import (
    is_network_runtime_request,
    run_network_http,
    stream_network_http,
)
from modules.network.presentation.runtime_environment_dependency import (
    enforce_public_network_runtime_environment,
)
from shared.infra.errors import AuthorizationError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.security.principal import ProjectApiPrincipal

router = APIRouter(prefix="/v1", tags=["public-runtime"])


def _runtime_principal(request: FastAPIRequest) -> ProjectApiPrincipal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal) or principal.kind != "runtime":
        raise AuthorizationError("Runtime Key authentication required")
    if principal.target_type not in {"agent", "network"}:
        raise AuthorizationError("Runtime Key binding is incomplete")
    return principal


@router.post("/run")
async def run(request: FastAPIRequest):
    if is_network_runtime_request(request):
        await enforce_public_network_runtime_environment(request)
        return await run_network_http(request)
    handler = public_run_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/run/stream")
async def run_stream(request: FastAPIRequest):
    if is_network_runtime_request(request):
        await enforce_public_network_runtime_environment(request)
        return await stream_network_http(request)
    handler = public_stream_composer()
    return await handler(request)


@router.get("/runs/{run_id}/stream")
async def reattach_run(run_id: UUID, request: FastAPIRequest):
    principal = _runtime_principal(request)
    if principal.target_type == "network":
        return await attach_network_run_composer()(run_id, request)
    return await attach_agent_run(run_id, request)


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: UUID, request: FastAPIRequest):
    principal = _runtime_principal(request)
    if principal.target_type == "network":
        response = await request_adapter(
            request,
            cancel_runtime_network_execution_composer(),
        )
        return response_adapter(response)
    return await cancel_agent_run(run_id, request)


@router.get("/sessions/{session_id}/active-run")
async def active_session_run(session_id: UUID, request: FastAPIRequest):
    principal = _runtime_principal(request)
    if principal.target_type == "network":
        return await active_network_run_composer()(
            request,
            network_session_id=session_id,
        )
    return await active_agent_run(request, session_id=session_id)


@router.post("/jobs", status_code=501)
async def create_job(_: FastAPIRequest):
    raise HTTPException(
        status_code=501,
        detail="Runtime Jobs are coming soon and are not enabled in the MVP",
    )


@router.get("/jobs/{job_id}", status_code=501)
async def get_job(_: FastAPIRequest, job_id: str):
    del job_id
    raise HTTPException(
        status_code=501,
        detail="Runtime Jobs are coming soon and are not enabled in the MVP",
    )
