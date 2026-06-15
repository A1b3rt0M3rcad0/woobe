from modules.billing.domain.enums import (
    BillingInterval,
    BillingProvider,
    PaymentEventStatus,
    PlanStatus,
    SubscriptionStatus,
)


class TestBillingInterval:
    def test_all_values(self):
        values = {v.value for v in BillingInterval}
        assert values == {"monthly", "yearly", "weekly", "daily"}


class TestPlanStatus:
    def test_all_values(self):
        values = {v.value for v in PlanStatus}
        assert values == {"active", "inactive", "archived"}


class TestSubscriptionStatus:
    def test_all_values(self):
        values = {v.value for v in SubscriptionStatus}
        assert values == {"active", "trialing", "past_due", "canceled", "incomplete", "incomplete_expired"}


class TestBillingProvider:
    def test_all_values(self):
        values = {v.value for v in BillingProvider}
        assert values == {"stripe", "paddle", "custom"}


class TestPaymentEventStatus:
    def test_all_values(self):
        values = {v.value for v in PaymentEventStatus}
        assert values == {"pending", "processed", "failed"}
