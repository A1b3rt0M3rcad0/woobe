from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import ListOrganizationsUseCase
from modules.identity.presentation.controllers.list_organizations_controller import ListOrganizationsController
from shared.infra.transactional_handler import TransactionalHandler


def list_organizations_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = ListOrganizationsUseCase(uow.organizations)
    controller = ListOrganizationsController(use_case)
    return TransactionalHandler(uow, controller.handle)
