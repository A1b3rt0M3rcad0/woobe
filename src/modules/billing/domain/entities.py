from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import uuid6

from modules.billing.domain.enums import (
    BillingInterval,
    BillingProvider,
    PaymentEventStatus,
    PlanStatus,
    SubscriptionStatus,
)


@dataclass
class Plan:
    id: UUID = field(default_factory=uuid6.uuid7)
    code: str = ""
    name: str = ""
    price_usd: float = 0.0
    billing_interval: BillingInterval = BillingInterval.monthly
    limits: dict | None = None
    status: PlanStatus = PlanStatus.active
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Customer:
    id: UUID = field(default_factory=uuid6.uuid7)
    organization_id: UUID = field(default_factory=uuid6.uuid7)
    provider: BillingProvider = BillingProvider.custom
    provider_customer_id: str = ""
    email: str = ""
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Subscription:
    id: UUID = field(default_factory=uuid6.uuid7)
    organization_id: UUID = field(default_factory=uuid6.uuid7)
    customer_id: UUID = field(default_factory=uuid6.uuid7)
    plan_id: UUID = field(default_factory=uuid6.uuid7)
    provider: BillingProvider = BillingProvider.custom
    provider_subscription_id: str = ""
    status: SubscriptionStatus = SubscriptionStatus.active
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class PaymentEvent:
    id: UUID = field(default_factory=uuid6.uuid7)
    provider: BillingProvider = BillingProvider.custom
    provider_event_id: str = ""
    event_type: str = ""
    payload: dict | None = None
    status: PaymentEventStatus = PaymentEventStatus.pending
    processed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
