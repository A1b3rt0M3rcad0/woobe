from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePlanInput(BaseModel):
    code: str
    name: str
    price_usd: float
    billing_interval: str = "monthly"
    limits: dict | None = None
    status: str = "active"


class CreatePlanOutput(BaseModel):
    plan_id: UUID


class CreateCustomerInput(BaseModel):
    organization_id: UUID
    provider: str = "custom"
    provider_customer_id: str = ""
    email: str = ""
    data: dict | None = None


class CreateCustomerOutput(BaseModel):
    customer_id: UUID


class CreateSubscriptionInput(BaseModel):
    organization_id: UUID
    customer_id: UUID
    plan_id: UUID
    provider: str = "custom"
    provider_subscription_id: str = ""
    status: str = "active"
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None


class CreateSubscriptionOutput(BaseModel):
    subscription_id: UUID


class CreatePaymentEventInput(BaseModel):
    provider: str
    provider_event_id: str
    event_type: str
    payload: dict | None = None
    subscription_id: UUID | None = None


class CreatePaymentEventOutput(BaseModel):
    event_id: UUID
