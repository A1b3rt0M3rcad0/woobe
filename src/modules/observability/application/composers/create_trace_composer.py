from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.application.use_cases import CreateTraceUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.create_trace_controller import CreateTraceController
from shared.infra.transactional_handler import TransactionalHandler


def create_trace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(session_factory)
    use_case = CreateTraceUseCase(uow.traces, uow.outbox)
    controller = CreateTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
