from fastapi import APIRouter, Request as FastAPIRequest

from modules.metering.composition.composers.get_agent_daily_usage_composer import (
    get_agent_daily_usage_composer,
)
from modules.metering.composition.composers.get_project_daily_usage_composer import (
    get_project_daily_usage_composer,
)
from modules.metering.composition.composers.get_project_usage_composer import (
    get_project_usage_composer,
)
from shared.infra.errors import AuthorizationError
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/metering", tags=["metering"])


@router.post("/usage-events", status_code=201)
async def record_usage(request: FastAPIRequest):
    del request
    raise AuthorizationError("Usage events are recorded by internal runtime services")


@router.get("/projects/{project_id}/usage")
async def get_project_usage(request: FastAPIRequest):
    handler = get_project_usage_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}/daily")
async def get_project_daily_usage(request: FastAPIRequest):
    handler = get_project_daily_usage_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/daily")
async def get_agent_daily_usage(request: FastAPIRequest):
    handler = get_agent_daily_usage_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
