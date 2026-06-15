from modules.billing.infra.database.models import (
    CustomerModel,
    InboxEventModel,
    OutboxEventModel,
    PaymentEventModel,
    PlanModel,
    SubscriptionModel,
)
from modules.billing.infra.database.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyPaymentEventRepository,
    SQLAlchemyPlanRepository,
    SQLAlchemySubscriptionRepository,
)
from modules.billing.infra.database.mappers import (
    customer_entity_to_model,
    customer_model_to_entity,
    payment_event_entity_to_model,
    payment_event_model_to_entity,
    plan_entity_to_model,
    plan_model_to_entity,
    subscription_entity_to_model,
    subscription_model_to_entity,
)


class TestCanonicalModelImports:
    def test_plan_model_importable(self):
        assert PlanModel.__tablename__ == "plans"

    def test_customer_model_importable(self):
        assert CustomerModel.__tablename__ == "customers"

    def test_subscription_model_importable(self):
        assert SubscriptionModel.__tablename__ == "subscriptions"

    def test_payment_event_model_importable(self):
        assert PaymentEventModel.__tablename__ == "payment_events"

    def test_outbox_model_importable(self):
        assert OutboxEventModel.__tablename__ == "outbox_events"

    def test_inbox_model_importable(self):
        assert InboxEventModel.__tablename__ == "inbox_events"


class TestCanonicalRepositoryImports:
    def test_plan_repository_importable(self):
        assert SQLAlchemyPlanRepository is not None

    def test_customer_repository_importable(self):
        assert SQLAlchemyCustomerRepository is not None

    def test_subscription_repository_importable(self):
        assert SQLAlchemySubscriptionRepository is not None

    def test_payment_event_repository_importable(self):
        assert SQLAlchemyPaymentEventRepository is not None

    def test_outbox_writer_importable(self):
        assert SQLAlchemyOutboxEventWriter is not None


class TestCanonicalMapperImports:
    def test_plan_mappers_importable(self):
        assert callable(plan_model_to_entity)
        assert callable(plan_entity_to_model)

    def test_customer_mappers_importable(self):
        assert callable(customer_model_to_entity)
        assert callable(customer_entity_to_model)

    def test_subscription_mappers_importable(self):
        assert callable(subscription_model_to_entity)
        assert callable(subscription_entity_to_model)

    def test_payment_event_mappers_importable(self):
        assert callable(payment_event_model_to_entity)
        assert callable(payment_event_entity_to_model)
