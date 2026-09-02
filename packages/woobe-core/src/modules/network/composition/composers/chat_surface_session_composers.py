from modules.network.application.use_cases.chat_surface_session import (
    CloseNetworkChatSurfaceSessionUseCase,
    CreateNetworkChatSurfaceSessionUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.chat_surface_session_repository import (
    SQLAlchemyNetworkChatSurfaceSessionRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.chat_surface_session_controllers import (
    CloseNetworkChatSurfaceSessionController,
    CreateNetworkChatSurfaceSessionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_network_chat_surface_session_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkChatSurfaceSessionRepository(uow)
    use_case = CreateNetworkChatSurfaceSessionUseCase(repository)
    controller = CreateNetworkChatSurfaceSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)


def close_network_chat_surface_session_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkChatSurfaceSessionRepository(uow)
    use_case = CloseNetworkChatSurfaceSessionUseCase(repository)
    controller = CloseNetworkChatSurfaceSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "close_network_chat_surface_session_composer",
    "create_network_chat_surface_session_composer",
]
