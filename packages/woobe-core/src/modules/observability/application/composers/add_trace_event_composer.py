from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.application.use_cases import CreateTraceEventUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.add_trace_event_controller import AddTraceEventController
from shared.infra.transactional_handler import TransactionalHandler


def add_trace_event_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(session_factory)
    use_case = CreateTraceEventUseCase(uow.trace_events, uow.outbox)
    controller = AddTraceEventController(use_case)
    return TransactionalHandler(uow, controller.handle)
