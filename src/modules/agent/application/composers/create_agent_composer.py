from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.agent.application.use_cases import CreateAgentUseCase
from modules.agent.presentation.controllers.create_agent_controller import CreateAgentController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    agent_repo = uow.agents
    credential_repo = uow.provider_credentials
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)
    controller = CreateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
