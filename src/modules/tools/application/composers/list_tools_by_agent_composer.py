from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyToolRepository
from modules.tools.application.use_cases import ListToolsByAgentUseCase
from modules.tools.presentation.controllers.list_tools_by_agent_controller import ListToolsByAgentController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_tools_by_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyToolRepository(uow)
    use_case = ListToolsByAgentUseCase(repo)
    controller = ListToolsByAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
