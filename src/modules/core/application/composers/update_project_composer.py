from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyProjectRepository
from modules.core.application.use_cases import UpdateProjectUseCase
from modules.core.presentation.controllers.update_project_controller import UpdateProjectController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def update_project_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyProjectRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateProjectUseCase(repo, outbox)
    controller = UpdateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
