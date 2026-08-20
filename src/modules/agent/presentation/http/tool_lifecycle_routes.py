from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.composition.composers.tools_composers import (
    get_tool_usage_impact_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/tools/{tool_id}/usage-impact")
async def get_tool_usage_impact(request: FastAPIRequest):
    handler = get_tool_usage_impact_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
