import pytest

from modules.billing.domain.errors import (
    PlanNotFoundError,
    CustomerNotFoundError,
    SubscriptionNotFoundError,
)
from shared.infra.errors import NotFoundError, DomainError


class TestPlanNotFoundError:
    def test_inheritance(self):
        err = PlanNotFoundError("plan not found")
        assert isinstance(err, PlanNotFoundError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, DomainError)

    def test_message(self):
        err = PlanNotFoundError("Plan pro not found")
        assert str(err) == "Plan pro not found"

    def test_can_be_raised(self):
        with pytest.raises(PlanNotFoundError):
            raise PlanNotFoundError("test")


class TestCustomerNotFoundError:
    def test_inheritance(self):
        err = CustomerNotFoundError("customer not found")
        assert isinstance(err, CustomerNotFoundError)
        assert isinstance(err, NotFoundError)

    def test_can_be_raised(self):
        with pytest.raises(CustomerNotFoundError):
            raise CustomerNotFoundError("test")


class TestSubscriptionNotFoundError:
    def test_inheritance(self):
        err = SubscriptionNotFoundError("subscription not found")
        assert isinstance(err, SubscriptionNotFoundError)
        assert isinstance(err, NotFoundError)

    def test_can_be_raised(self):
        with pytest.raises(SubscriptionNotFoundError):
            raise SubscriptionNotFoundError("test")
