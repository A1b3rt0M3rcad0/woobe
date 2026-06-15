from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.database.repositories import SQLAlchemySubscriptionRepository
from modules.billing.infra.database.unit_of_work import BillingUnitOfWork
from modules.billing.application.use_cases import GetOrganizationSubscriptionUseCase
from modules.billing.presentation.controllers.get_organization_subscription_controller import GetOrganizationSubscriptionController
from shared.application.transactional_handler import TransactionalHandler


def get_organization_subscription_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = BillingUnitOfWork(session_factory)
    repo = SQLAlchemySubscriptionRepository(uow)
    use_case = GetOrganizationSubscriptionUseCase(repo)
    controller = GetOrganizationSubscriptionController(use_case)
    return TransactionalHandler(uow, controller.handle)
