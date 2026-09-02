from modules.chat_surface.application.use_cases.session_read import (
    GetChatSurfaceActivityUseCase,
    ListChatSurfaceSessionsUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE
from modules.chat_surface.infra.database.session_read_repository import (
    SQLAlchemyChatSurfaceSessionReadRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.presentation.controllers.session_read_controllers import (
    GetChatSurfaceActivityController,
    ListChatSurfaceSessionsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_chat_surface_sessions_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceSessionReadRepository(uow)
    use_case = ListChatSurfaceSessionsUseCase(repository)
    controller = ListChatSurfaceSessionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_chat_surface_activity_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceSessionReadRepository(uow)
    use_case = GetChatSurfaceActivityUseCase(repository)
    controller = GetChatSurfaceActivityController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "get_chat_surface_activity_composer",
    "list_chat_surface_sessions_composer",
]
