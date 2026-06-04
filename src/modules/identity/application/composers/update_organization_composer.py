from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOrganizationRepository, SQLAlchemyOutboxEventWriter
from modules.identity.service.use_cases import UpdateOrganizationUseCase
from modules.identity.presentation.controllers.update_organization_controller import UpdateOrganizationController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def update_organization_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    org_repo = SQLAlchemyOrganizationRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateOrganizationUseCase(org_repo, outbox)
    controller = UpdateOrganizationController(use_case)
    return TransactionalHandler(uow, controller.handle)
