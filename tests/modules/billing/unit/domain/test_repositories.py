from abc import ABC

from modules.billing.domain.repositories import (
    CustomerRepository,
    PaymentEventRepository,
    PlanRepository,
    SubscriptionRepository,
)


class TestPlanRepository:
    def test_is_abstract(self):
        assert issubclass(PlanRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(PlanRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(PlanRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(PlanRepository.delete, "__isabstractmethod__", False)


class TestCustomerRepository:
    def test_is_abstract(self):
        assert issubclass(CustomerRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(CustomerRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(CustomerRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(CustomerRepository.delete, "__isabstractmethod__", False)


class TestSubscriptionRepository:
    def test_is_abstract(self):
        assert issubclass(SubscriptionRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(SubscriptionRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(SubscriptionRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(SubscriptionRepository.delete, "__isabstractmethod__", False)


class TestPaymentEventRepository:
    def test_is_abstract(self):
        assert issubclass(PaymentEventRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(PaymentEventRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(PaymentEventRepository.get_by_id, "__isabstractmethod__", False)
