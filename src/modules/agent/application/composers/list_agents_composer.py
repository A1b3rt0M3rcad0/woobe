from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentRepository
from modules.agent.application.use_cases.ai_use_cases import ListAgentsUseCase
from modules.ai.presentation.controllers.list_agents_controller import ListAgentsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_agents_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentRepository(uow)
    use_case = ListAgentsUseCase(repo)
    controller = ListAgentsController(use_case)
    return TransactionalHandler(uow, controller.handle)
