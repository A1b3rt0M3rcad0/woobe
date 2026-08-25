from fastapi import APIRouter, Request as FastAPIRequest

from modules.observability.application.composers.list_traces_composer import list_traces_composer
from modules.observability.application.composers.get_trace_composer import get_trace_composer
from shared.infra.errors import AuthorizationError
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces")
async def list_traces(request: FastAPIRequest):
    handler = list_traces_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/traces", status_code=201)
async def create_trace(request: FastAPIRequest):
    del request
    raise AuthorizationError("Traces are written by internal runtime services")


@router.post("/traces/{trace_id}/events", status_code=201)
async def add_trace_event(request: FastAPIRequest):
    del request
    raise AuthorizationError("Trace events are written by internal runtime services")


@router.get("/traces/{trace_id}")
async def get_trace(request: FastAPIRequest):
    handler = get_trace_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
