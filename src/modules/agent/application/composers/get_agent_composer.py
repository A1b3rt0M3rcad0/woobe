from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository
from modules.agent.application.use_cases.ai_use_cases import GetAgentByIdUseCase
from modules.agent.presentation.controllers.get_agent_controller import GetAgentController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentRepository(uow)
    use_case = GetAgentByIdUseCase(repo)
    controller = GetAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
