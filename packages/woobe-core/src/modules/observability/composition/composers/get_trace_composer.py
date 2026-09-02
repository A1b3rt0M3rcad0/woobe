from modules.observability.application.use_cases import GetTraceUseCase
from modules.observability.composition.resources import DATABASE_ENGINE
from modules.observability.infra.database.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.get_trace_controller import GetTraceController
from shared.infra.transactional_handler import TransactionalHandler


def get_trace_composer() -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(DATABASE_ENGINE)
    trace_repository = SQLAlchemyTraceRepository(uow)
    event_repository = SQLAlchemyTraceEventRepository(uow)
    use_case = GetTraceUseCase(trace_repository, event_repository)
    controller = GetTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
