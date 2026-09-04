from modules.observability.composition.resources import DATABASE_ENGINE
from modules.observability.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.observability.infra.database.repositories import SQLAlchemyTraceRepository
from modules.observability.application.use_cases import CreateTraceUseCase
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.create_trace_controller import CreateTraceController
from shared.infra.transactional_handler import TransactionalHandler


def create_trace_composer() -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(DATABASE_ENGINE)
    use_case = CreateTraceUseCase(SQLAlchemyTraceRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = CreateTraceController(use_case)
    return TransactionalHandler(uow, controller.handle)
