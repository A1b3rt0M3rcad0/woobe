from collections.abc import Callable

from modules.chat_surface.application.use_cases.message_lifecycle import (
    BeginChatSurfaceMessageUseCase,
    LatestChatSurfaceMessageUseCase,
    MarkChatSurfaceMessageUseCase,
)
from modules.chat_surface.composition.integrations.message_runtime import (
    ChatSurfaceMessageRuntime,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.chat_surface.infra.database.message_request_repository import (
    SQLAlchemyChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.presentation.controllers.message_lifecycle_controllers import (
    BeginChatSurfaceMessageController,
    LatestChatSurfaceMessageController,
    MarkChatSurfaceMessageController,
)
from shared.infra.transactional_handler import TransactionalHandler


def begin_chat_surface_message_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
    use_case = BeginChatSurfaceMessageUseCase(
        repository,
        max_metadata_bytes=SETTINGS.runtime_max_metadata_bytes,
    )
    controller = BeginChatSurfaceMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)


def latest_chat_surface_message_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
    use_case = LatestChatSurfaceMessageUseCase(repository)
    controller = LatestChatSurfaceMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)


def mark_chat_surface_message_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
    use_case = MarkChatSurfaceMessageUseCase(repository)
    controller = MarkChatSurfaceMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)


def begin_chat_surface_message_runtime_composer() -> Callable:
    runtime = ChatSurfaceMessageRuntime()
    return runtime.begin


def mark_chat_surface_message_runtime_composer() -> Callable:
    runtime = ChatSurfaceMessageRuntime()
    return runtime.mark


__all__ = [
    "begin_chat_surface_message_composer",
    "begin_chat_surface_message_runtime_composer",
    "latest_chat_surface_message_composer",
    "mark_chat_surface_message_composer",
    "mark_chat_surface_message_runtime_composer",
]
