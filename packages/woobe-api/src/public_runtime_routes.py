from uuid import UUID

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from chat_surface_runtime_routes import router as chat_surface_runtime_router
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
    submit_public_network_run_composer,
    wait_network_run_composer,
)
from shared.infra.errors import AuthorizationError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.security.principal import ProjectApiPrincipal

router = APIRouter(prefix="/v1", tags=["public-runtime"])
router.include_router(chat_surface_runtime_router)


def _runtime_principal(request: FastAPIRequest) -> ProjectApiPrincipal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal) or principal.kind != "runtime":
        raise AuthorizationError("Runtime Key authentication required")
    if principal.target_type not in {"agent", "network"}:
        raise AuthorizationError("Runtime Key binding is incomplete")
    return principal


def _is_network_runtime_request(request: FastAPIRequest) -> bool:
    principal = getattr(request.state, "principal", None)
    return (
        isinstance(principal, ProjectApiPrincipal)
        and principal.kind == "runtime"
        and principal.target_type == "network"
    )


async def _submit_network_run(request: FastAPIRequest) -> UUID:
    accepted = await request_adapter(request, submit_public_network_run_composer())
    return UUID(str(accepted.body["data"]["execution_id"]))


@router.post("/run")
async def run(request: FastAPIRequest):
    if _is_network_runtime_request(request):
        run_id = await _submit_network_run(request)
        return await wait_network_run_composer()(run_id, request)
    handler = public_run_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/run/stream")
async def run_stream(request: FastAPIRequest):
    if _is_network_runtime_request(request):
        run_id = await _submit_network_run(request)
        return await attach_network_run_composer()(run_id, request)
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
