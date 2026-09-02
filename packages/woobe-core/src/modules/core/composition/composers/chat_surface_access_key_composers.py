from modules.core.application.use_cases.chat_surface_access_key import (
    AuthenticateChatSurfaceAccessKeyUseCase,
    CreateChatSurfaceAccessKeyUseCase,
    ListChatSurfaceAccessKeysUseCase,
    RevokeChatSurfaceAccessKeyUseCase,
    RotateChatSurfaceAccessKeyUseCase,
)
from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.chat_surface_access_key_repository import (
    SQLAlchemyChatSurfaceAccessKeyRepository,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer
from modules.core.presentation.controllers.chat_surface_access_key_controllers import (
    AuthenticateChatSurfaceAccessKeyController,
    CreateChatSurfaceAccessKeyController,
    ListChatSurfaceAccessKeysController,
    RevokeChatSurfaceAccessKeyController,
    RotateChatSurfaceAccessKeyController,
)
from shared.infra.transactional_handler import TransactionalHandler


def authenticate_chat_surface_access_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceAccessKeyRepository(uow)
    use_case = AuthenticateChatSurfaceAccessKeyUseCase(repository)
    controller = AuthenticateChatSurfaceAccessKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_chat_surface_access_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceAccessKeyRepository(uow)
    use_case = CreateChatSurfaceAccessKeyUseCase(repository, SharedApiKeyIssuer())
    controller = CreateChatSurfaceAccessKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_chat_surface_access_keys_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceAccessKeyRepository(uow)
    use_case = ListChatSurfaceAccessKeysUseCase(repository)
    controller = ListChatSurfaceAccessKeysController(use_case)
    return TransactionalHandler(uow, controller.handle)


def revoke_chat_surface_access_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceAccessKeyRepository(uow)
    use_case = RevokeChatSurfaceAccessKeyUseCase(repository)
    controller = RevokeChatSurfaceAccessKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)


def rotate_chat_surface_access_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfaceAccessKeyRepository(uow)
    use_case = RotateChatSurfaceAccessKeyUseCase(repository, SharedApiKeyIssuer())
    controller = RotateChatSurfaceAccessKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "authenticate_chat_surface_access_key_composer",
    "create_chat_surface_access_key_composer",
    "list_chat_surface_access_keys_composer",
    "revoke_chat_surface_access_key_composer",
    "rotate_chat_surface_access_key_composer",
]
