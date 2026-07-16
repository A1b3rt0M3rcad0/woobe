from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.application.composers.public_runtime_composers import (
    public_create_job_composer,
    public_get_job_composer,
    public_run_composer,
    public_stream_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/v1", tags=["public-runtime"])


@router.post("/run")
async def run(request: FastAPIRequest):
    handler = public_run_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/run/stream")
async def run_stream(request: FastAPIRequest):
    handler = public_stream_composer(request.app.state.session_factory)
    return await handler(request)


@router.post("/jobs", status_code=201)
async def create_job(request: FastAPIRequest):
    handler = public_create_job_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/jobs/{job_id}")
async def get_job(request: FastAPIRequest):
    handler = public_get_job_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
