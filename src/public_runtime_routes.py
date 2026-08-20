from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from modules.agent.entrypoint import public_run_composer, public_stream_composer
from modules.network.presentation.public_runtime import (
    is_network_runtime_request,
    run_network_http,
    stream_network_http,
)
from modules.network.presentation.runtime_environment_dependency import (
    enforce_public_network_runtime_environment,
)
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/v1", tags=["public-runtime"])


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
