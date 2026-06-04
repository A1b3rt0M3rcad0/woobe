from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemySubscriptionRepository
from modules.billing.service.use_cases import CreateSubscriptionUseCase
from modules.billing.presentation.controllers.create_subscription_controller import CreateSubscriptionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_subscription_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    sub_repo = SQLAlchemySubscriptionRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateSubscriptionUseCase(sub_repo, outbox)
    controller = CreateSubscriptionController(use_case)
    return TransactionalHandler(uow, controller.handle)
