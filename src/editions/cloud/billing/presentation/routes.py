from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from editions.cloud.billing.application.composers.list_plans_composer import list_plans_composer
from editions.cloud.billing.application.composers.get_organization_subscription_composer import get_organization_subscription_composer
from shared.infra.errors import AuthenticationError, AuthorizationError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.security.organization_access import OrganizationAccessService

router = APIRouter(prefix="/billing", tags=["billing"])


def _principal_user_id(request: FastAPIRequest) -> UUID:
    principal = getattr(request.state, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        raise AuthenticationError("Authentication required")
    return UUID(str(user_id))


@router.post("/plans", status_code=201)
async def create_plan(request: FastAPIRequest):
    del request
    raise AuthorizationError("Billing plans are managed internally")


@router.get("/plans")
async def list_plans(request: FastAPIRequest):
    handler = list_plans_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/subscriptions", status_code=201)
async def create_subscription(request: FastAPIRequest):
    del request
    raise AuthorizationError("Subscriptions are provisioned by the trusted billing flow")


@router.get("/organizations/{org_id}/subscription")
async def get_organization_subscription(request: FastAPIRequest, org_id: str):
    await OrganizationAccessService(request.app.state.session_factory).require_admin(
        _principal_user_id(request),
        UUID(org_id),
    )
    handler = get_organization_subscription_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
