from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.infra.repositories import SQLAlchemyProjectRepository
from modules.core.service.use_cases import GetProjectByIdUseCase
from modules.core.presentation.controllers.get_project_controller import GetProjectController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_project_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyProjectRepository(uow)
    use_case = GetProjectByIdUseCase(repo)
    controller = GetProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
