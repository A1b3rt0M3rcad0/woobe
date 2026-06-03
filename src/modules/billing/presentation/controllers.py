from uuid import UUID

from fastapi import APIRouter, Depends

from modules.billing.application.providers import BillingProviders
from modules.billing.presentation.schemas import (
    CreatePlanRequest,
    CreateSubscriptionRequest,
    PlanResponse,
    SubscriptionResponse,
)
from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, error, ok

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/plans", status_code=201)
async def create_plan(
    body: CreatePlanRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = BillingProviders(manager.session)
    result = await providers.create_plan_use_case().execute(body)
    return created({"plan_id": str(result.plan_id)})


@router.get("/plans")
async def list_plans(
    manager: SessionManager = Depends(get_session_manager),
):
    providers = BillingProviders(manager.session)
    plans = await providers.list_active_plans()
    return ok(
        [
            PlanResponse(
                id=p.id,
                code=p.code,
                name=p.name,
                price_usd=p.price_usd,
                status=str(p.status),
            )
            for p in plans
        ]
    )


@router.post("/subscriptions", status_code=201)
async def create_subscription(
    body: CreateSubscriptionRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = BillingProviders(manager.session)
    result = await providers.create_subscription_use_case().execute(body)
    return created({"subscription_id": str(result.subscription_id)})


@router.get("/organizations/{org_id}/subscription")
async def get_organization_subscription(
    org_id: UUID,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = BillingProviders(manager.session)
    subscription = await providers.get_organization_subscription(org_id)
    if subscription is None:
        return error("Subscription not found", status_code=404)
    return ok(
        SubscriptionResponse(
            id=subscription.id,
            organization_id=subscription.organization_id,
            plan_id=subscription.plan_id,
            status=str(subscription.status),
            current_period_end=subscription.current_period_end,
        )
    )
