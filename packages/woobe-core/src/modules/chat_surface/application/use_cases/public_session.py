import json

from modules.chat_surface.application.dtos.public_session import (
    ArchiveChatSurfaceSessionBindingInput,
    ChatSurfaceSessionBindingState,
    ChatSurfaceSessionTokenResult,
    CreateChatSurfaceSessionBindingInput,
    GetChatSurfaceSessionBindingInput,
    GetChatSurfaceSessionByIdempotencyInput,
    IssueChatSurfaceSessionTokenInput,
)
from modules.chat_surface.application.interfaces.public_session_repository import (
    ChatSurfacePublicSessionRepository,
)
from modules.chat_surface.application.interfaces.session_authorization import (
    ChatSessionTokenIssuer,
)
from modules.chat_surface.application.use_cases.session_authorization import (
    CONTROL_PLANE_TEST_SOURCE,
)
from modules.chat_surface.domain.origin import normalize_origin
from shared.contracts.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


class GetChatSurfaceSessionByIdempotencyUseCase:
    def __init__(self, repository: ChatSurfacePublicSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: GetChatSurfaceSessionByIdempotencyInput,
    ) -> ChatSurfaceSessionBindingState | None:
        normalized = input_dto.idempotency_key.strip()
        if not normalized or len(normalized) > 255:
            raise ValidationError("A valid Idempotency-Key is required")
        return await self._repository.get_by_idempotency(
            input_dto.surface_id,
            normalized,
        )


class GetChatSurfaceSessionBindingUseCase:
    def __init__(self, repository: ChatSurfacePublicSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: GetChatSurfaceSessionBindingInput,
    ) -> ChatSurfaceSessionBindingState:
        binding = await self._repository.get_binding(
            input_dto.surface_id,
            input_dto.session_id,
        )
        if binding is None:
            raise NotFoundError("ChatSurface Session not found")
        return binding


class CreateChatSurfaceSessionBindingUseCase:
    def __init__(
        self,
        repository: ChatSurfacePublicSessionRepository,
        *,
        max_metadata_bytes: int,
    ) -> None:
        self._repository = repository
        self._max_metadata_bytes = max_metadata_bytes

    async def execute(
        self,
        input_dto: CreateChatSurfaceSessionBindingInput,
    ) -> ChatSurfaceSessionBindingState:
        normalized = input_dto.idempotency_key.strip()
        if not normalized or len(normalized) > 255:
            raise ValidationError("A valid Idempotency-Key is required")
        if input_dto.metadata is not None:
            encoded = json.dumps(
                input_dto.metadata,
                separators=(",", ":"),
                default=str,
            ).encode()
            if len(encoded) > self._max_metadata_bytes:
                raise ValidationError("ChatSurface metadata is too large")

        existing = await self._repository.get_by_idempotency(
            input_dto.surface_id,
            normalized,
        )
        if existing is not None:
            return existing

        surface = await self._repository.get_surface(
            input_dto.surface_id,
            for_update=True,
        )
        if surface is None:
            raise NotFoundError("ChatSurface not found")
        if surface.status != "active":
            raise ConflictError("ChatSurface is not active")
        if (
            surface.project_id != input_dto.expected_project_id
            or surface.target_type != input_dto.expected_target_type
            or surface.target_id != input_dto.expected_target_id
            or surface.target_release_id != input_dto.expected_target_release_id
        ):
            raise ConflictError("ChatSurface changed while creating Session; retry")
        return await self._repository.create_binding(
            input_dto,
            idempotency_key=normalized,
        )


class IssueChatSurfaceSessionTokenUseCase:
    def __init__(
        self,
        repository: ChatSurfacePublicSessionRepository,
        token_issuer: ChatSessionTokenIssuer,
        *,
        allow_insecure_origins: bool,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._allow_insecure_origins = allow_insecure_origins

    async def execute(
        self,
        input_dto: IssueChatSurfaceSessionTokenInput,
    ) -> ChatSurfaceSessionTokenResult:
        surface = await self._repository.get_surface(input_dto.surface_id)
        if surface is None:
            raise NotFoundError("ChatSurface not found")
        if surface.status != "active":
            raise ConflictError("ChatSurface is not active")

        binding = await self._repository.get_binding(
            input_dto.surface_id,
            input_dto.session_id,
        )
        if (
            binding is None
            or binding.status != "active"
            or binding.project_id != surface.project_id
            or binding.target_type != surface.target_type
            or binding.target_id != surface.target_id
        ):
            raise ConflictError("ChatSurface Session is not active")

        normalized_origin = normalize_origin(
            input_dto.origin,
            allow_insecure=self._allow_insecure_origins,
        )
        metadata = binding.metadata or {}
        if (
            metadata.get("source") != CONTROL_PLANE_TEST_SOURCE
            and normalized_origin not in set(surface.allowed_origins)
        ):
            raise AuthorizationError("Origin is not allowed by this ChatSurface")

        token = self._token_issuer.issue(
            project_id=surface.project_id,
            chat_surface_id=surface.id,
            target_type=surface.target_type,
            target_id=surface.target_id,
            target_release_id=binding.target_release_id,
            session_id=binding.session_id,
            origin=normalized_origin,
            surface_credential_id=input_dto.surface_credential_id,
            token_epoch=surface.token_epoch,
            ttl_seconds=surface.session_token_ttl_seconds,
        )
        return ChatSurfaceSessionTokenResult(
            session_id=binding.session_id,
            target_release_id=binding.target_release_id,
            token=token,
            expires_in=surface.session_token_ttl_seconds,
        )


class ArchiveChatSurfaceSessionBindingUseCase:
    def __init__(self, repository: ChatSurfacePublicSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ArchiveChatSurfaceSessionBindingInput,
    ) -> ChatSurfaceSessionBindingState:
        binding = await self._repository.get_binding(
            input_dto.surface_id,
            input_dto.session_id,
            for_update=True,
        )
        if binding is None:
            raise NotFoundError("ChatSurface Session not found")
        if binding.status == "archived":
            return binding
        return await self._repository.archive_binding(
            input_dto.surface_id,
            input_dto.session_id,
        )


__all__ = [
    "ArchiveChatSurfaceSessionBindingUseCase",
    "CreateChatSurfaceSessionBindingUseCase",
    "GetChatSurfaceSessionBindingUseCase",
    "GetChatSurfaceSessionByIdempotencyUseCase",
    "IssueChatSurfaceSessionTokenUseCase",
]
