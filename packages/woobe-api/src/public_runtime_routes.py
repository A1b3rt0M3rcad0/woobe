from uuid import UUID

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from runtime_composition import RUNTIME_HTTP
from shared.infra.errors import AuthorizationError
from shared.security.principal import ProjectApiPrincipal
from woobe_api.http.shared.runtime_contract_validation import (
    RuntimeContractsValidationRequest,
)

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
    return await RUNTIME_HTTP.run(request)


@router.post("/run/stream")
async def run_stream(request: FastAPIRequest):
    return await RUNTIME_HTTP.stream(request)


@router.get("/runs/{run_id}/stream")
async def reattach_run(run_id: UUID, request: FastAPIRequest):
    principal = _runtime_principal(request)
    return await RUNTIME_HTTP.reattach(principal.target_type, run_id, request)


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: UUID, request: FastAPIRequest):
    principal = _runtime_principal(request)
    return await RUNTIME_HTTP.cancel(principal.target_type, run_id, request)


@router.get("/sessions/{session_id}/active-run")
async def active_session_run(session_id: UUID, request: FastAPIRequest):
    principal = _runtime_principal(request)
    return await RUNTIME_HTTP.active(principal.target_type, session_id, request)


@router.post("/contracts/validate")
async def validate_runtime_contracts(request: FastAPIRequest):
    principal = _runtime_principal(request)
    payload = RuntimeContractsValidationRequest(**(await request.json()))
    return await RUNTIME_HTTP.validate_contracts(
        principal,
        output_contract=payload.output_contract,
        external_context=payload.external_context,
    )


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
