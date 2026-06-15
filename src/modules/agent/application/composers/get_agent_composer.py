from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import GetAgentByIdUseCase
from modules.agent.presentation.controllers.get_agent_controller import GetAgentController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def get_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.agents
    use_case = GetAgentByIdUseCase(repo)
    controller = GetAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
