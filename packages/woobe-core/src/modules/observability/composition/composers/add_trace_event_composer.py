from modules.observability.composition.resources import DATABASE_ENGINE
from modules.observability.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.observability.infra.database.repositories import SQLAlchemyTraceEventRepository
from modules.observability.application.use_cases import CreateTraceEventUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.add_trace_event_controller import AddTraceEventController
from shared.infra.transactional_handler import TransactionalHandler


def add_trace_event_composer() -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(DATABASE_ENGINE)
    use_case = CreateTraceEventUseCase(SQLAlchemyTraceEventRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = AddTraceEventController(use_case)
    return TransactionalHandler(uow, controller.handle)
