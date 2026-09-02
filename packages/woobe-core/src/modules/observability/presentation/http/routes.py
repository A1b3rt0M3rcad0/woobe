from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import JSONResponse

from modules.observability.composition.composers.get_trace_composer import (
    get_trace_composer,
)
from modules.observability.composition.composers.list_traces_composer import (
    list_traces_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces")
async def list_traces(request: FastAPIRequest):
    handler = list_traces_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/traces", status_code=201)
async def create_trace(request: FastAPIRequest):
    del request
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "message": "Traces are written by internal runtime services",
            "data": None,
        },
    )


@router.post("/traces/{trace_id}/events", status_code=201)
async def add_trace_event(request: FastAPIRequest):
    del request
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "message": "Trace events are written by internal runtime services",
            "data": None,
        },
    )


@router.get("/traces/{trace_id}")
async def get_trace(request: FastAPIRequest):
    handler = get_trace_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
