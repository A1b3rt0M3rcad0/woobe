from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import CreateOrganizationUseCase
from modules.identity.presentation.controllers.create_organization_controller import CreateOrganizationController
from shared.infra.transactional_handler import TransactionalHandler


def create_organization_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = CreateOrganizationUseCase(uow.organizations, uow.outbox)
    controller = CreateOrganizationController(use_case)
    return TransactionalHandler(uow, controller.handle)
