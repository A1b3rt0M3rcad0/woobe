from modules.chat_surface.application.use_cases.message_lifecycle import (
    MarkChatSurfaceMessageUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE
from modules.chat_surface.infra.database.message_request_repository import (
    SQLAlchemyChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.presentation.controllers.message_lifecycle_controllers import (
    MarkChatSurfaceMessageController,
)
from shared.infra.transactional_handler import TransactionalHandler


def mark_chat_surface_message_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
    use_case = MarkChatSurfaceMessageUseCase(repository)
    controller = MarkChatSurfaceMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = ["mark_chat_surface_message_composer"]
