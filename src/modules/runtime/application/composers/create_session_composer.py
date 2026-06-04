from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.runtime.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemySessionRepository
from modules.runtime.service.use_cases import CreateSessionUseCase
from modules.runtime.presentation.controllers.create_session_controller import CreateSessionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_session_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemySessionRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateSessionUseCase(repo, outbox)
    controller = CreateSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
