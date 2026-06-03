from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePlanRequest(BaseModel):
    code: str
    name: str
    price_usd: float
    billing_interval: str = "monthly"
    limits: dict | None = None


class PlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    price_usd: float
    status: str


class CreateSubscriptionRequest(BaseModel):
    organization_id: UUID
    customer_id: UUID
    plan_id: UUID
    provider: str = "custom"
    provider_subscription_id: str = ""


class SubscriptionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    plan_id: UUID
    status: str
    current_period_end: datetime | None = None
