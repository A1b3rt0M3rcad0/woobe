from modules.observability.composition.resources import DATABASE_ENGINE
from modules.observability.infra.database.repositories import SQLAlchemyTraceEventRepository
from modules.observability.infra.database.repositories import SQLAlchemyTraceRepository
from modules.observability.application.use_cases import GetTraceUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.get_trace_controller import GetTraceController
from shared.infra.transactional_handler import TransactionalHandler


def get_trace_composer() -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(DATABASE_ENGINE)
    use_case = GetTraceUseCase(SQLAlchemyTraceRepository(uow), SQLAlchemyTraceEventRepository(uow))
    controller = GetTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
