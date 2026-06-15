from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import UpdateOrganizationUseCase
from modules.identity.presentation.controllers.update_organization_controller import UpdateOrganizationController
from shared.infra.transactional_handler import TransactionalHandler


def update_organization_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = UpdateOrganizationUseCase(uow.organizations, uow.outbox)
    controller = UpdateOrganizationController(use_case)
    return TransactionalHandler(uow, controller.handle)
