from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyProjectRepository
from modules.core.service.use_cases import CreateProjectUseCase
from modules.core.presentation.controllers.create_project_controller import CreateProjectController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_project_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    project_repo = SQLAlchemyProjectRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateProjectUseCase(project_repo, outbox)
    controller = CreateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
