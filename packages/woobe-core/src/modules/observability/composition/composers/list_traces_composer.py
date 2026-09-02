from modules.observability.application.use_cases import ListTracesUseCase
from modules.observability.composition.resources import DATABASE_ENGINE
from modules.observability.infra.database.repositories import SQLAlchemyTraceRepository
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.presentation.controllers.list_traces_controller import (
    ListTracesController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_traces_composer() -> TransactionalHandler:
    uow = ObservabilityUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyTraceRepository(uow)
    use_case = ListTracesUseCase(repository)
    controller = ListTracesController(use_case)
    return TransactionalHandler(uow, controller.handle)
