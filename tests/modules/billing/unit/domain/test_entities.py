from uuid import UUID

from modules.billing.domain.entities import Plan, Customer, Subscription, PaymentEvent
from modules.billing.domain.enums import (
    BillingInterval,
    BillingProvider,
    PaymentEventStatus,
    PlanStatus,
    SubscriptionStatus,
)


class TestPlan:
    def test_create_with_defaults(self):
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

    def test_create_with_values(self):
        plan = Plan(
            code="pro",
            name="Professional",
            price_usd=29.99,
            billing_interval=BillingInterval.yearly,
            limits={"agents": 10},
            status=PlanStatus.active,
        )
        assert plan.code == "pro"
        assert plan.name == "Professional"
        assert plan.price_usd == 29.99
        assert plan.billing_interval == BillingInterval.yearly
        assert plan.limits == {"agents": 10}


class TestCustomer:
    def test_create_with_defaults(self):
        customer = Customer()
        assert isinstance(customer.id, UUID)
        assert isinstance(customer.organization_id, UUID)
        assert customer.provider == BillingProvider.custom
        assert customer.email == ""

    def test_create_with_values(self):
        oid = UUID("00000000-0000-0000-0000-000000000001")
        customer = Customer(
            organization_id=oid,
            provider=BillingProvider.stripe,
            provider_customer_id="cus_123",
            email="billing@example.com",
        )
        assert customer.organization_id == oid
        assert customer.provider == BillingProvider.stripe
        assert customer.provider_customer_id == "cus_123"


class TestSubscription:
    def test_create_with_defaults(self):
        sub = Subscription()
        assert isinstance(sub.id, UUID)
        assert isinstance(sub.organization_id, UUID)
        assert isinstance(sub.customer_id, UUID)
        assert isinstance(sub.plan_id, UUID)
        assert sub.status == SubscriptionStatus.active

    def test_create_with_values(self):
        sub = Subscription(
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
            customer_id=UUID("00000000-0000-0000-0000-000000000002"),
            plan_id=UUID("00000000-0000-0000-0000-000000000003"),
            provider=BillingProvider.stripe,
            status=SubscriptionStatus.trialing,
        )
        assert sub.status == SubscriptionStatus.trialing
        assert sub.provider == BillingProvider.stripe


class TestPaymentEvent:
    def test_create_with_defaults(self):
        event = PaymentEvent()
        assert isinstance(event.id, UUID)
        assert event.event_type == ""
        assert event.status == PaymentEventStatus.pending

    def test_create_with_values(self):
        event = PaymentEvent(
            provider=BillingProvider.stripe,
            provider_event_id="evt_123",
            event_type="invoice.paid",
            payload={"amount": 2999},
            status=PaymentEventStatus.processed,
        )
        assert event.provider == BillingProvider.stripe
        assert event.event_type == "invoice.paid"
        assert event.payload == {"amount": 2999}
        assert event.status == PaymentEventStatus.processed
