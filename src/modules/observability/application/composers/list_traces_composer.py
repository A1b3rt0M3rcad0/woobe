from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.application.use_cases import ListTracesUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.list_traces_controller import ListTracesController
from shared.infra.transactional_handler import TransactionalHandler


def list_traces_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(session_factory)
    use_case = ListTracesUseCase(uow.traces)
    controller = ListTracesController(use_case)
    return TransactionalHandler(uow, controller.handle)
