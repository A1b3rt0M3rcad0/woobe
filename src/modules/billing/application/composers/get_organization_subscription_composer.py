from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.repositories import SQLAlchemySubscriptionRepository
from modules.billing.application.use_cases import GetOrganizationSubscriptionUseCase
from modules.billing.presentation.controllers.get_organization_subscription_controller import GetOrganizationSubscriptionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_organization_subscription_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemySubscriptionRepository(uow)
    use_case = GetOrganizationSubscriptionUseCase(repo)
    controller = GetOrganizationSubscriptionController(use_case)
    return TransactionalHandler(uow, controller.handle)
