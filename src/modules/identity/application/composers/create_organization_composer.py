from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOrganizationRepository, SQLAlchemyOutboxEventWriter
from modules.identity.service.use_cases import CreateOrganizationUseCase
from modules.identity.presentation.controllers.create_organization_controller import CreateOrganizationController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_organization_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    org_repo = SQLAlchemyOrganizationRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateOrganizationUseCase(org_repo, outbox)
    controller = CreateOrganizationController(use_case)
    return TransactionalHandler(uow, controller.handle)
