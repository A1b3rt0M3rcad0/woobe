"""Explicit transport-neutral public surface for ChatSurface hosts."""

from modules.chat_surface.application.runtime_gateway import (
    ChatRunIdentity,
    ChatMessageRequestSnapshot,
    ChatRuntimeChunk,
    ChatRuntimeGateway,
    ChatRuntimeRequest,
    ChatRuntimeTarget,
    DisconnectCheck,
    PreparedChatRuntime,
)
from modules.chat_surface.infra.services.control_plane_service import (
    CONTROL_PLANE_TEST_SOURCE,
    ControlPlaneChatSurfaceService,
)
from modules.chat_surface.composition.services import build_chat_surface_service
from modules.chat_surface.application.dtos import (
    CreateChatSurfaceRequest,
    CreateSurfaceAccessKeyRequest,
    CreateSurfaceSessionRequest,
    IssueSessionTokenRequest,
    StreamChatMessageRequest,
    UpdateChatSurfaceRequest,
)
from modules.chat_surface.infra.services.chat_surface_service import surface_payload

__all__ = [
    "CONTROL_PLANE_TEST_SOURCE",
    "ChatRunIdentity",
    "ChatMessageRequestSnapshot",
    "ChatRuntimeChunk",
    "ChatRuntimeGateway",
    "ChatRuntimeRequest",
    "ChatRuntimeTarget",
    "ControlPlaneChatSurfaceService",
    "CreateChatSurfaceRequest",
    "CreateSurfaceAccessKeyRequest",
    "CreateSurfaceSessionRequest",
    "DisconnectCheck",
    "IssueSessionTokenRequest",
    "PreparedChatRuntime",
    "StreamChatMessageRequest",
    "UpdateChatSurfaceRequest",
    "surface_payload",
    "build_chat_surface_service",
]
