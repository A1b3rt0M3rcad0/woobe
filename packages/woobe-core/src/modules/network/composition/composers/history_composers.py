from modules.network.application.use_cases.history_use_cases import (
    ListNetworkExecutionEventsUseCase,
    ListNetworkSessionMessagesUseCase,
    ListNetworkSessionsUseCase,
    ResetNetworkSessionContextUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.history_repository import (
    SQLAlchemyNetworkHistoryRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.history_controllers import (
    ListNetworkExecutionEventsController,
    ListNetworkSessionMessagesController,
    ListNetworkSessionsController,
    ResetNetworkSessionContextController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_network_sessions_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkHistoryRepository(uow)
    use_case = ListNetworkSessionsUseCase(repository)
    controller = ListNetworkSessionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_network_session_messages_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkHistoryRepository(uow)
    use_case = ListNetworkSessionMessagesUseCase(repository)
    controller = ListNetworkSessionMessagesController(use_case)
    return TransactionalHandler(uow, controller.handle)


def reset_network_session_context_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkHistoryRepository(uow)
    use_case = ResetNetworkSessionContextUseCase(repository)
    controller = ResetNetworkSessionContextController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_network_execution_events_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkHistoryRepository(uow)
    use_case = ListNetworkExecutionEventsUseCase(repository)
    controller = ListNetworkExecutionEventsController(use_case)
    return TransactionalHandler(uow, controller.handle)
