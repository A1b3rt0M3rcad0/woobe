from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import GetOrganizationUseCase
from modules.identity.presentation.controllers.get_organization_controller import GetOrganizationController
from shared.application.transactional_handler import TransactionalHandler


def get_organization_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = GetOrganizationUseCase(uow.organizations)
    controller = GetOrganizationController(use_case)
    return TransactionalHandler(uow, controller.handle)
