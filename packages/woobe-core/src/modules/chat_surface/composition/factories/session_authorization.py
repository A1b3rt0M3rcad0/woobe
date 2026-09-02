from modules.chat_surface.application.interfaces.session_authorization import (
    ChatSurfaceCredentialReader,
    ChatSurfaceTargetSessionAuthorizer,
)
from modules.chat_surface.application.use_cases.session_authorization import (
    AuthorizeChatSurfaceSessionUseCase,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.chat_surface.infra.database.session_authorization_repository import (
    SQLAlchemyChatSurfaceSessionAuthorizationRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.chat_surface.infra.security.session_token_codec import ChatSessionTokenCodec
from modules.chat_surface.presentation.controllers.session_authorization_controller import (
    AuthorizeChatSurfaceSessionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def build_chat_surface_session_authorization_handler(
    credential_reader: ChatSurfaceCredentialReader,
    target_authorizer: ChatSurfaceTargetSessionAuthorizer,
) -> TransactionalHandler:
    uow = ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceSessionAuthorizationRepository(uow)
    token_decoder = ChatSessionTokenCodec(
        signing_key=SETTINGS.chat_token_signing_key or SETTINGS.secret_key,
        issuer=SETTINGS.chat_token_issuer,
        audience=SETTINGS.chat_token_audience,
        ttl_seconds=SETTINGS.chat_token_ttl_seconds,
        leeway_seconds=SETTINGS.auth_clock_skew_seconds,
    )
    use_case = AuthorizeChatSurfaceSessionUseCase(
        repository,
        token_decoder,
        credential_reader,
        target_authorizer,
        allow_insecure_origins=SETTINGS.chat_surface_allow_insecure_origins,
        environment=SETTINGS.environment,
    )
    controller = AuthorizeChatSurfaceSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = ["build_chat_surface_session_authorization_handler"]
