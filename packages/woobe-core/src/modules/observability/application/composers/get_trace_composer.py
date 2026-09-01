from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.application.use_cases import GetTraceUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.get_trace_controller import GetTraceController
from shared.infra.transactional_handler import TransactionalHandler


def get_trace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(session_factory)
    use_case = GetTraceUseCase(uow.traces, uow.trace_events)
    controller = GetTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
