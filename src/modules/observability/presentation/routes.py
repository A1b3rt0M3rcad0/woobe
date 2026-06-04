from fastapi import APIRouter, Request as FastAPIRequest

from modules.observability.application.composers.list_traces_composer import list_traces_composer
from modules.observability.application.composers.create_trace_composer import create_trace_composer
from modules.observability.application.composers.add_trace_event_composer import add_trace_event_composer
from modules.observability.application.composers.get_trace_composer import get_trace_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces")
async def list_traces(request: FastAPIRequest):
    handler = list_traces_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/traces", status_code=201)
async def create_trace(request: FastAPIRequest):
    handler = create_trace_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/traces/{trace_id}/events", status_code=201)
async def add_trace_event(request: FastAPIRequest):
    handler = add_trace_event_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/traces/{trace_id}")
async def get_trace(request: FastAPIRequest):
    handler = get_trace_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
