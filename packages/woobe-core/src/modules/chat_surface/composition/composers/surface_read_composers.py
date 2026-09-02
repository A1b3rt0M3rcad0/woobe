from modules.chat_surface.application.use_cases.surface_read import (
    GetChatSurfaceUseCase,
    ListChatSurfacesUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE
from modules.chat_surface.infra.database.surface_read_repository import (
    SQLAlchemyChatSurfaceReadRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.presentation.controllers.surface_read_controllers import (
    GetChatSurfaceController,
    ListChatSurfacesController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_chat_surfaces_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceReadRepository(uow)
    use_case = ListChatSurfacesUseCase(repository)
    controller = ListChatSurfacesController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceReadRepository(uow)
    use_case = GetChatSurfaceUseCase(repository)
    controller = GetChatSurfaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = ["get_chat_surface_composer", "list_chat_surfaces_composer"]
