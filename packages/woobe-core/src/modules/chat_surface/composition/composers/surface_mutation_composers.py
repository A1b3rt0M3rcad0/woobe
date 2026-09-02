from modules.chat_surface.application.use_cases.surface_mutation import (
    ActivateChatSurfaceUseCase,
    ArchiveChatSurfaceUseCase,
    CreateChatSurfaceUseCase,
    DisableChatSurfaceUseCase,
    RefreshChatSurfaceReleaseUseCase,
    UpdateChatSurfaceUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.chat_surface.infra.database.surface_mutation_repository import (
    SQLAlchemyChatSurfaceMutationRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.presentation.controllers.surface_mutation_controllers import (
    ActivateChatSurfaceController,
    ArchiveChatSurfaceController,
    CreateChatSurfaceController,
    DisableChatSurfaceController,
    RefreshChatSurfaceReleaseController,
    UpdateChatSurfaceController,
)
from shared.infra.transactional_handler import TransactionalHandler


def _allow_insecure_origins() -> bool:
    local_environment = SETTINGS.environment.strip().lower() in {
        "development",
        "dev",
        "test",
        "local",
    }
    return SETTINGS.chat_surface_allow_insecure_origins or local_environment


def create_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    use_case = CreateChatSurfaceUseCase(
        repository,
        allow_insecure_origins=_allow_insecure_origins(),
    )
    controller = CreateChatSurfaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    use_case = UpdateChatSurfaceUseCase(
        repository,
        allow_insecure_origins=_allow_insecure_origins(),
    )
    controller = UpdateChatSurfaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


def refresh_chat_surface_release_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    use_case = RefreshChatSurfaceReleaseUseCase(repository)
    controller = RefreshChatSurfaceReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)


def activate_chat_surface_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceMutationRepository(uow)
    use_case = ActivateChatSurfaceUseCase(repository)
    controller = ActivateChatSurfaceController(use_case)
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
    "activate_chat_surface_composer",
    "archive_chat_surface_composer",
    "create_chat_surface_composer",
    "disable_chat_surface_composer",
    "refresh_chat_surface_release_composer",
    "update_chat_surface_composer",
]
