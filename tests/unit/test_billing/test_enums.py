from editions.cloud.billing.domain.enums import (
    BillingInterval,
    PlanStatus,
    SubscriptionStatus,
    BillingProvider,
    PaymentEventStatus,
)


class TestBillingInterval:
    def test_members(self):
        assert BillingInterval.monthly.value == "monthly"
        assert BillingInterval.yearly.value == "yearly"
        assert BillingInterval.weekly.value == "weekly"
        assert BillingInterval.daily.value == "daily"

    def test_is_str_enum(self):
        assert issubclass(BillingInterval, str)


class TestPlanStatus:
    def test_members(self):
        assert PlanStatus.active.value == "active"
        assert PlanStatus.inactive.value == "inactive"
        assert PlanStatus.archived.value == "archived"

    def test_is_str_enum(self):
        assert issubclass(PlanStatus, str)


class TestSubscriptionStatus:
    def test_members(self):
        assert SubscriptionStatus.active.value == "active"
        assert SubscriptionStatus.trialing.value == "trialing"
        assert SubscriptionStatus.past_due.value == "past_due"
        assert SubscriptionStatus.canceled.value == "canceled"
        assert SubscriptionStatus.incomplete.value == "incomplete"
        assert SubscriptionStatus.incomplete_expired.value == "incomplete_expired"

    def test_is_str_enum(self):
        assert issubclass(SubscriptionStatus, str)


class TestBillingProvider:
    def test_members(self):
        assert BillingProvider.stripe.value == "stripe"
        assert BillingProvider.paddle.value == "paddle"
        assert BillingProvider.custom.value == "custom"

    def test_is_str_enum(self):
        assert issubclass(BillingProvider, str)


class TestPaymentEventStatus:
    def test_members(self):
        assert PaymentEventStatus.pending.value == "pending"
        assert PaymentEventStatus.processed.value == "processed"
        assert PaymentEventStatus.failed.value == "failed"

    def test_is_str_enum(self):
        assert issubclass(PaymentEventStatus, str)
