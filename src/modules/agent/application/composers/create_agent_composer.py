from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository, SQLAlchemyOutboxEventWriter, SQLAlchemyProviderCredentialRepository
from modules.agent.application.use_cases.ai_use_cases import CreateAgentUseCase
from modules.agent.presentation.controllers.create_agent_controller import CreateAgentController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    agent_repo = SQLAlchemyAgentRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)
    controller = CreateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
