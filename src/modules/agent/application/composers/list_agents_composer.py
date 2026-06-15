from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import ListAgentsUseCase
from modules.agent.presentation.controllers.list_agents_controller import ListAgentsController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_agents_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.agents
    use_case = ListAgentsUseCase(repo)
    controller = ListAgentsController(use_case)
    return TransactionalHandler(uow, controller.handle)
