from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.database.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemySubscriptionRepository
from modules.billing.infra.database.unit_of_work import BillingUnitOfWork
from modules.billing.application.use_cases import CreateSubscriptionUseCase
from modules.billing.presentation.controllers.create_subscription_controller import CreateSubscriptionController
from shared.infra.transactional_handler import TransactionalHandler


def create_subscription_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = BillingUnitOfWork(session_factory)
    sub_repo = SQLAlchemySubscriptionRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateSubscriptionUseCase(sub_repo, outbox)
    controller = CreateSubscriptionController(use_case)
    return TransactionalHandler(uow, controller.handle)
