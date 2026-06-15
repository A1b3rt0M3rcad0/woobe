from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyToolRepository
from modules.tools.application.use_cases import ListToolsUseCase
from modules.tools.presentation.controllers.list_tools_controller import ListToolsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_tools_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyToolRepository(uow)
    use_case = ListToolsUseCase(repo)
    controller = ListToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)
