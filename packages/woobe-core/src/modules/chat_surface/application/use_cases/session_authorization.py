from datetime import UTC, datetime

from modules.chat_surface.application.dtos.session_authorization import (
    AuthorizeChatSurfaceSessionInput,
    AuthorizedChatSession,
    ChatSessionClaims,
    ChatSurfaceSessionAuthorizationSnapshot,
    TargetSessionAuthorizationInput,
)
from modules.chat_surface.application.interfaces.session_authorization import (
    ChatSessionTokenDecoder,
    ChatSurfaceCredentialReader,
    ChatSurfaceSessionAuthorizationRepository,
    ChatSurfaceTargetSessionAuthorizer,
)
from modules.chat_surface.domain.origin import normalize_origin
from shared.contracts.errors import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
)


CONTROL_PLANE_TEST_SOURCE = "control_plane_test"


def _authorize_snapshot(
    snapshot: ChatSurfaceSessionAuthorizationSnapshot,
    claims: ChatSessionClaims,
    *,
    now: datetime | None = None,
) -> AuthorizedChatSession:
    surface = snapshot.surface
    if (
        surface is None
        or surface.status != "active"
        or surface.project_id != claims.project_id
        or surface.target_type != claims.target_type
        or surface.target_id != claims.target_id
        or surface.token_epoch != claims.token_epoch
    ):
        raise AuthenticationError("ChatSurface Session token is inactive")

    binding = snapshot.binding
    if (
        binding is None
        or binding.status != "active"
        or binding.chat_surface_id != surface.id
        or binding.project_id != claims.project_id
        or binding.target_type != claims.target_type
        or binding.target_id != claims.target_id
        or binding.target_release_id != claims.target_release_id
        or binding.session_id != claims.session_id
    ):
        raise NotFoundError("ChatSurface Session not found")

    metadata = binding.metadata or {}
    is_control_plane_test = metadata.get("source") == CONTROL_PLANE_TEST_SOURCE
    credential = snapshot.credential

    if is_control_plane_test:
        if (
            binding.surface_credential_id != claims.surface_credential_id
            or credential is not None
        ):
            raise AuthenticationError("ChatSurface test Session token is inactive")
    else:
        if claims.origin not in set(surface.allowed_origins):
            raise AuthenticationError("ChatSurface Session token is inactive")
        current = (now or datetime.now(UTC)).astimezone(UTC)
        expires_at = credential.expires_at if credential is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if (
            credential is None
            or credential.id != claims.surface_credential_id
            or credential.kind != "chat_surface"
            or credential.project_id != surface.project_id
            or credential.chat_surface_id != surface.id
            or credential.status != "active"
            or credential.revoked_at is not None
            or (expires_at is not None and expires_at <= current)
        ):
            raise AuthenticationError("ChatSurface Session token is inactive")

    return AuthorizedChatSession(
        surface=surface,
        binding=binding,
        claims=claims,
    )


class AuthorizeChatSurfaceSessionUseCase:
    def __init__(
        self,
        repository: ChatSurfaceSessionAuthorizationRepository,
        token_decoder: ChatSessionTokenDecoder,
        credential_reader: ChatSurfaceCredentialReader,
        target_authorizer: ChatSurfaceTargetSessionAuthorizer,
        *,
        allow_insecure_origins: bool,
        environment: str,
    ) -> None:
        self._repository = repository
        self._token_decoder = token_decoder
        self._credential_reader = credential_reader
        self._target_authorizer = target_authorizer
        self._allow_insecure_origins = (
            allow_insecure_origins
            or environment.strip().lower() in {"development", "dev", "test", "local"}
        )

    async def execute(
        self,
        input_dto: AuthorizeChatSurfaceSessionInput,
    ) -> AuthorizedChatSession:
        claims = ChatSessionClaims.model_validate(
            self._token_decoder.decode(input_dto.token),
            from_attributes=True,
        )
        if claims.session_id != input_dto.expected_session_id:
            raise NotFoundError("ChatSurface Session not found")
        if input_dto.permission not in claims.permissions:
            raise AuthorizationError("ChatSurface Session token scope is insufficient")

        normalized_host_origin = normalize_origin(
            input_dto.host_origin,
            allow_insecure=self._allow_insecure_origins,
        )
        if normalized_host_origin != claims.origin:
            raise AuthorizationError("ChatSurface Session origin does not match")

        snapshot = await self._repository.load(claims)
        credential = await self._credential_reader.get(claims.surface_credential_id)
        snapshot = snapshot.model_copy(update={"credential": credential})
        authorized = _authorize_snapshot(snapshot, claims)
        target_authorized = await self._target_authorizer.is_authorized(
            TargetSessionAuthorizationInput(
                project_id=authorized.surface.project_id,
                target_type=authorized.surface.target_type,
                target_id=authorized.surface.target_id,
                target_release_id=authorized.binding.target_release_id,
                session_id=authorized.binding.session_id,
                chat_surface_id=authorized.surface.id,
            )
        )
        if not target_authorized:
            raise NotFoundError("ChatSurface Session not found")
        return authorized


__all__ = [
    "AuthorizeChatSurfaceSessionUseCase",
    "CONTROL_PLANE_TEST_SOURCE",
]
