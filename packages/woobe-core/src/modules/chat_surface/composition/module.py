from modules.chat_surface.application.dtos.message_request import MessageRequestState
from modules.chat_surface.application.dtos.session_authorization import (
    AuthorizedChatSession,
    ChatSurfaceCredentialAuthorizationState,
    TargetSessionAuthorizationInput,
)
from modules.chat_surface.application.interfaces.session_authorization import (
    ChatSurfaceCredentialReader,
    ChatSurfaceTargetSessionAuthorizer,
)
from modules.chat_surface.application.use_cases.session_authorization import (
    CONTROL_PLANE_TEST_SOURCE,
)
from modules.chat_surface.composition.composers.message_lifecycle_composers import (
    begin_chat_surface_message_runtime_composer,
    latest_chat_surface_message_composer,
    mark_chat_surface_message_composer,
    mark_chat_surface_message_runtime_composer,
)
from modules.chat_surface.composition.composers.public_session_composers import (
    archive_chat_surface_session_binding_composer,
    create_chat_surface_session_binding_composer,
    get_chat_surface_session_binding_composer,
    get_chat_surface_session_by_idempotency_composer,
    issue_chat_surface_session_token_composer,
)
from modules.chat_surface.composition.composers.surface_mutation_composers import (
    activate_chat_surface_composer,
    create_chat_surface_composer,
    refresh_chat_surface_release_composer,
)
from modules.chat_surface.composition.factories.session_authorization import (
    build_chat_surface_session_authorization_handler,
)
from modules.chat_surface.infra.security.session_token_codec import ChatSessionTokenCodec
from modules.chat_surface.presentation.http.routes import router as chat_surface_router
from modules.chat_surface.presentation.schemas import (
    StreamChatMessageRequest,
    normalize_appearance_config,
)


CHAT_SURFACE_HTTP_ROUTERS = (chat_surface_router,)


__all__ = [
    "AuthorizedChatSession",
    "CHAT_SURFACE_HTTP_ROUTERS",
    "CONTROL_PLANE_TEST_SOURCE",
    "ChatSessionTokenCodec",
    "ChatSurfaceCredentialAuthorizationState",
    "ChatSurfaceCredentialReader",
    "ChatSurfaceTargetSessionAuthorizer",
    "MessageRequestState",
    "StreamChatMessageRequest",
    "TargetSessionAuthorizationInput",
    "activate_chat_surface_composer",
    "archive_chat_surface_session_binding_composer",
    "begin_chat_surface_message_runtime_composer",
    "build_chat_surface_session_authorization_handler",
    "create_chat_surface_composer",
    "create_chat_surface_session_binding_composer",
    "get_chat_surface_session_binding_composer",
    "get_chat_surface_session_by_idempotency_composer",
    "issue_chat_surface_session_token_composer",
    "latest_chat_surface_message_composer",
    "mark_chat_surface_message_composer",
    "mark_chat_surface_message_runtime_composer",
    "normalize_appearance_config",
    "refresh_chat_surface_release_composer",
]
