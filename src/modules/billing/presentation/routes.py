from fastapi import APIRouter, Request as FastAPIRequest

from modules.billing.application.composers.create_plan_composer import create_plan_composer
from modules.billing.application.composers.list_plans_composer import list_plans_composer
from modules.billing.application.composers.create_subscription_composer import create_subscription_composer
from modules.billing.application.composers.get_organization_subscription_composer import get_organization_subscription_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/plans", status_code=201)
async def create_plan(request: FastAPIRequest):
    handler = create_plan_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/plans")
async def list_plans(request: FastAPIRequest):
    handler = list_plans_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/subscriptions", status_code=201)
async def create_subscription(request: FastAPIRequest):
    handler = create_subscription_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/subscription")
async def get_organization_subscription(request: FastAPIRequest):
    handler = get_organization_subscription_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
