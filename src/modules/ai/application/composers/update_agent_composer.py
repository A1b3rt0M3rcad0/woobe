from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentRepository, SQLAlchemyOutboxEventWriter, SQLAlchemyProviderCredentialRepository
from modules.ai.service.use_cases import UpdateAgentUseCase
from modules.ai.presentation.controllers.update_agent_controller import UpdateAgentController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def update_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    agent_repo = SQLAlchemyAgentRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateAgentUseCase(agent_repo, credential_repo, outbox)
    controller = UpdateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
