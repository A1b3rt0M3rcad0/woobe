from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyRuntimeOutboxEventWriter
from modules.agent.application.use_cases import CreateSessionUseCase
from modules.agent.presentation.controllers.create_session_controller import CreateSessionController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_session_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.sessions
    outbox = SQLAlchemyRuntimeOutboxEventWriter(uow)
    use_case = CreateSessionUseCase(repo, outbox)
    controller = CreateSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
