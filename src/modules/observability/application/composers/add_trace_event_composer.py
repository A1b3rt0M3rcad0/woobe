from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyTraceEventRepository
from modules.observability.application.use_cases import CreateTraceEventUseCase
from modules.observability.presentation.controllers.add_trace_event_controller import AddTraceEventController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def add_trace_event_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    event_repo = SQLAlchemyTraceEventRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateTraceEventUseCase(event_repo, outbox)
    controller = AddTraceEventController(use_case)
    return TransactionalHandler(uow, controller.handle)
