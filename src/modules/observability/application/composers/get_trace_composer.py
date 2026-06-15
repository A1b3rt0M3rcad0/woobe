from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.infra.repositories import SQLAlchemyTraceEventRepository, SQLAlchemyTraceRepository
from modules.observability.application.use_cases import GetTraceUseCase
from modules.observability.presentation.controllers.get_trace_controller import GetTraceController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_trace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    trace_repo = SQLAlchemyTraceRepository(uow)
    event_repo = SQLAlchemyTraceEventRepository(uow)
    use_case = GetTraceUseCase(trace_repo, event_repo)
    controller = GetTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
