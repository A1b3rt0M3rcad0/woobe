from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.infra.repositories import SQLAlchemyProjectRepository
from modules.core.application.use_cases import ListProjectsUseCase
from modules.core.presentation.controllers.list_projects_controller import ListProjectsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_projects_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyProjectRepository(uow)
    use_case = ListProjectsUseCase(repo)
    controller = ListProjectsController(use_case)
    return TransactionalHandler(uow, controller.handle)
