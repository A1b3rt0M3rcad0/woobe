from modules.chat_surface.application.use_cases.surface_mutation import (
    ArchiveChatSurfaceUseCase,
    DisableChatSurfaceUseCase,
    UpdateChatSurfaceUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.chat_surface.infra.database.surface_mutation_repository import (
    SQLAlchemyChatSurfaceMutationRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.presentation.controllers.surface_mutation_controllers import (
    ArchiveChatSurfaceController,
    DisableChatSurfaceController,
    UpdateChatSurfaceController,
)
from shared.infra.transactional_handler import TransactionalHandler


def update_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    local_environment = SETTINGS.environment.strip().lower() in {
        "development",
        "dev",
        "test",
        "local",
    }
    use_case = UpdateChatSurfaceUseCase(
        repository,
        allow_insecure_origins=(
            SETTINGS.chat_surface_allow_insecure_origins or local_environment
        ),
    )
    controller = UpdateChatSurfaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


def disable_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    use_case = DisableChatSurfaceUseCase(repository)
    controller = DisableChatSurfaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


def archive_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    use_case = ArchiveChatSurfaceUseCase(repository)
    controller = ArchiveChatSurfaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "archive_chat_surface_composer",
    "disable_chat_surface_composer",
    "update_chat_surface_composer",
]
