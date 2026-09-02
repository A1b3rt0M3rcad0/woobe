from modules.chat_surface.application.use_cases.public_session import (
    ArchiveChatSurfaceSessionBindingUseCase,
    CreateChatSurfaceSessionBindingUseCase,
    GetChatSurfaceSessionBindingUseCase,
    GetChatSurfaceSessionByIdempotencyUseCase,
    IssueChatSurfaceSessionTokenUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.chat_surface.infra.database.public_session_repository import (
    SQLAlchemyChatSurfacePublicSessionRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.infra.security.session_token_codec import ChatSessionTokenCodec
from modules.chat_surface.presentation.controllers.public_session_controllers import (
    ArchiveChatSurfaceSessionBindingController,
    CreateChatSurfaceSessionBindingController,
    GetChatSurfaceSessionBindingController,
    GetChatSurfaceSessionByIdempotencyController,
    IssueChatSurfaceSessionTokenController,
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


def _token_codec() -> ChatSessionTokenCodec:
    return ChatSessionTokenCodec(
        signing_key=SETTINGS.chat_token_signing_key or SETTINGS.secret_key,
        issuer=SETTINGS.chat_token_issuer,
        audience=SETTINGS.chat_token_audience,
        ttl_seconds=SETTINGS.chat_token_ttl_seconds,
        leeway_seconds=SETTINGS.auth_clock_skew_seconds,
    )


def get_chat_surface_session_by_idempotency_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfacePublicSessionRepository(uow)
    use_case = GetChatSurfaceSessionByIdempotencyUseCase(repository)
    controller = GetChatSurfaceSessionByIdempotencyController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_chat_surface_session_binding_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfacePublicSessionRepository(uow)
    use_case = GetChatSurfaceSessionBindingUseCase(repository)
    controller = GetChatSurfaceSessionBindingController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_chat_surface_session_binding_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfacePublicSessionRepository(uow)
    use_case = CreateChatSurfaceSessionBindingUseCase(
        repository,
        max_metadata_bytes=SETTINGS.runtime_max_metadata_bytes,
    )
    controller = CreateChatSurfaceSessionBindingController(use_case)
    return TransactionalHandler(uow, controller.handle)


def issue_chat_surface_session_token_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfacePublicSessionRepository(uow)
    use_case = IssueChatSurfaceSessionTokenUseCase(
        repository,
        _token_codec(),
        allow_insecure_origins=_allow_insecure_origins(),
    )
    controller = IssueChatSurfaceSessionTokenController(use_case)
    return TransactionalHandler(uow, controller.handle)


def archive_chat_surface_session_binding_composer() -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyChatSurfacePublicSessionRepository(uow)
    use_case = ArchiveChatSurfaceSessionBindingUseCase(repository)
    controller = ArchiveChatSurfaceSessionBindingController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "archive_chat_surface_session_binding_composer",
    "create_chat_surface_session_binding_composer",
    "get_chat_surface_session_binding_composer",
    "get_chat_surface_session_by_idempotency_composer",
    "issue_chat_surface_session_token_composer",
]
