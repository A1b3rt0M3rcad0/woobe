"""ChatSurface service factories for synchronous process hosts."""

from modules.chat_surface.application.runtime_gateway import ChatRuntimeGateway
from modules.chat_surface.application.security import ChatSessionTokenCodec
from modules.chat_surface.composition.resources import SESSION_FACTORY, SETTINGS
from modules.chat_surface.infra.services.control_plane_service import (
    ControlPlaneChatSurfaceService,
)


def build_chat_surface_service(
    runtime_gateway: ChatRuntimeGateway,
) -> ControlPlaneChatSurfaceService:
    local_environment = SETTINGS.environment.strip().lower() in {
        "development",
        "dev",
        "test",
        "local",
    }
    token_codec = ChatSessionTokenCodec(
        signing_key=SETTINGS.chat_token_signing_key or SETTINGS.secret_key,
        issuer=SETTINGS.chat_token_issuer,
        audience=SETTINGS.chat_token_audience,
        ttl_seconds=SETTINGS.chat_token_ttl_seconds,
        leeway_seconds=SETTINGS.auth_clock_skew_seconds,
    )
    return ControlPlaneChatSurfaceService(
        SESSION_FACTORY,
        token_codec,
        runtime_gateway=runtime_gateway,
        allow_insecure_origins=(
            SETTINGS.chat_surface_allow_insecure_origins or local_environment
        ),
        max_metadata_bytes=SETTINGS.runtime_max_metadata_bytes,
    )


__all__ = ["build_chat_surface_service"]
