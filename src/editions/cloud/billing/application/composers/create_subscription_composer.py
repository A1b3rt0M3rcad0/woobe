from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from editions.cloud.billing.infra.database.repositories import (
    SQLAlchemyCustomerRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyPlanRepository,
    SQLAlchemySubscriptionRepository,
)
from editions.cloud.billing.infra.database.unit_of_work import BillingUnitOfWork
from editions.cloud.billing.application.use_cases import CreateSubscriptionUseCase
from editions.cloud.billing.presentation.controllers.create_subscription_controller import CreateSubscriptionController
from shared.infra.transactional_handler import TransactionalHandler


def create_subscription_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = BillingUnitOfWork(session_factory)
    sub_repo = SQLAlchemySubscriptionRepository(uow)
    customer_repo = SQLAlchemyCustomerRepository(uow)
    plan_repo = SQLAlchemyPlanRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateSubscriptionUseCase(sub_repo, customer_repo, plan_repo, outbox)
    controller = CreateSubscriptionController(use_case)
    return TransactionalHandler(uow, controller.handle)
