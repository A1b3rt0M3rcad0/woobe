from __future__ import annotations

from enum import StrEnum, auto


class BillingInterval(StrEnum):
    monthly = auto()
    yearly = auto()
    weekly = auto()
    daily = auto()


class PlanStatus(StrEnum):
    active = auto()
    inactive = auto()
    archived = auto()


class SubscriptionStatus(StrEnum):
    active = auto()
    trialing = auto()
    past_due = auto()
    canceled = auto()
    incomplete = auto()
    incomplete_expired = auto()


class BillingProvider(StrEnum):
    stripe = auto()
    paddle = auto()
    custom = auto()


class PaymentEventStatus(StrEnum):
    pending = auto()
    processed = auto()
    failed = auto()
