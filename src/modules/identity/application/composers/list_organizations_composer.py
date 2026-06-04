from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOrganizationRepository
from modules.identity.service.use_cases import ListOrganizationsUseCase
from modules.identity.presentation.controllers.list_organizations_controller import ListOrganizationsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_organizations_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyOrganizationRepository(uow)
    use_case = ListOrganizationsUseCase(repo)
    controller = ListOrganizationsController(use_case)
    return TransactionalHandler(uow, controller.handle)
