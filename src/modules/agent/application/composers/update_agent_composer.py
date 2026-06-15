from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.agent.application.use_cases import UpdateAgentUseCase
from modules.agent.presentation.controllers.update_agent_controller import UpdateAgentController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def update_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    agent_repo = uow.agents
    credential_repo = uow.provider_credentials
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateAgentUseCase(agent_repo, credential_repo, outbox)
    controller = UpdateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
