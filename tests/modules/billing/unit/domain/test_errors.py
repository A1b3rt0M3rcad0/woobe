from modules.billing.domain.errors import CustomerNotFoundError, PlanNotFoundError, SubscriptionNotFoundError


class TestPlanNotFoundError:
    def test_is_exception(self):
        assert issubclass(PlanNotFoundError, Exception)

    def test_default_message(self):
        err = PlanNotFoundError("Plan not found")
        assert str(err) == "Plan not found"


class TestCustomerNotFoundError:
    def test_is_exception(self):
        assert issubclass(CustomerNotFoundError, Exception)

    def test_default_message(self):
        err = CustomerNotFoundError("Customer not found")
        assert str(err) == "Customer not found"


class TestSubscriptionNotFoundError:
    def test_is_exception(self):
        assert issubclass(SubscriptionNotFoundError, Exception)

    def test_default_message(self):
        err = SubscriptionNotFoundError("Subscription not found")
        assert str(err) == "Subscription not found"
