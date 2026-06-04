from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyTraceRepository
from modules.observability.service.use_cases import CreateTraceUseCase
from modules.observability.presentation.controllers.create_trace_controller import CreateTraceController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_trace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyTraceRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateTraceUseCase(repo, outbox)
    controller = CreateTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
