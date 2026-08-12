from uuid import UUID
from datetime import datetime

from editions.cloud.billing.domain.entities import Plan, Customer, Subscription, PaymentEvent
from editions.cloud.billing.domain.enums import (
    BillingInterval,
    PlanStatus,
    SubscriptionStatus,
    BillingProvider,
    PaymentEventStatus,
)


class TestPlan:
    def test_defaults(self):
        plan = Plan()
        assert isinstance(plan.id, UUID)
        assert plan.code == ""
        assert plan.name == ""
        assert plan.price_usd == 0.0
        assert plan.billing_interval == BillingInterval.monthly
        assert plan.limits is None
        assert plan.status == PlanStatus.active
        assert plan.created_at is None
        assert plan.updated_at is None

    def test_custom_values(self):
        plan = Plan(
            code="pro",
            name="Pro Plan",
            price_usd=29.99,
            billing_interval=BillingInterval.yearly,
            limits={"agents": 10, "tokens": 1_000_000},
            status=PlanStatus.active,
        )
        assert plan.code == "pro"
        assert plan.price_usd == 29.99
        assert plan.billing_interval == BillingInterval.yearly
        assert plan.limits == {"agents": 10, "tokens": 1_000_000}


class TestCustomer:
    def test_defaults(self):
        customer = Customer()
        assert isinstance(customer.id, UUID)
        assert isinstance(customer.organization_id, UUID)
        assert customer.provider == BillingProvider.custom
        assert customer.provider_customer_id == ""
        assert customer.email == ""
        assert customer.data is None

    def test_custom_values(self):
        customer = Customer(
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
            provider=BillingProvider.stripe,
            provider_customer_id="cus_123",
            email="org@test.com",
            data={"tier": "enterprise"},
        )
        assert customer.provider == BillingProvider.stripe
        assert customer.provider_customer_id == "cus_123"


class TestSubscription:
    def test_defaults(self):
        sub = Subscription()
        assert isinstance(sub.id, UUID)
        assert isinstance(sub.organization_id, UUID)
        assert isinstance(sub.customer_id, UUID)
        assert isinstance(sub.plan_id, UUID)
        assert sub.provider == BillingProvider.custom
        assert sub.status == SubscriptionStatus.active

    def test_custom_values(self):
        now = datetime.now()
        sub = Subscription(
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
            customer_id=UUID("00000000-0000-0000-0000-000000000002"),
            plan_id=UUID("00000000-0000-0000-0000-000000000003"),
            provider=BillingProvider.stripe,
            provider_subscription_id="sub_abc",
            status=SubscriptionStatus.trialing,
            current_period_start=now,
        )
        assert sub.provider_subscription_id == "sub_abc"
        assert sub.status == SubscriptionStatus.trialing


class TestPaymentEvent:
    def test_defaults(self):
        event = PaymentEvent()
        assert isinstance(event.id, UUID)
        assert event.provider == BillingProvider.custom
        assert event.provider_event_id == ""
        assert event.event_type == ""
        assert event.payload is None
        assert event.status == PaymentEventStatus.pending
        assert event.processed_at is None

    def test_custom_values(self):
        now = datetime.now()
        event = PaymentEvent(
            provider=BillingProvider.stripe,
            provider_event_id="evt_001",
            event_type="invoice.paid",
            payload={"amount": 2999},
            status=PaymentEventStatus.processed,
            processed_at=now,
        )
        assert event.event_type == "invoice.paid"
        assert event.status == PaymentEventStatus.processed
