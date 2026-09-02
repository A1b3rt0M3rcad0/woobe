from datetime import UTC, datetime
from hmac import compare_digest
from uuid import uuid4

from modules.core.application.dtos.chat_surface_access_key import (
    AuthenticateChatSurfaceAccessKeyInput,
    ChatSurfaceAccessKeyMutationResult,
    ChatSurfaceAccessKeyState,
    CreateChatSurfaceAccessKeyInput,
    ListChatSurfaceAccessKeysInput,
    PersistChatSurfaceAccessKeyInput,
    RevokeChatSurfaceAccessKeyInput,
    RotateChatSurfaceAccessKeyInput,
)
from modules.core.application.interfaces.api_key_issuer import ApiKeyIssuer
from modules.core.application.interfaces.chat_surface_access_key_repository import (
    ChatSurfaceAccessKeyRepository,
)
from shared.contracts.chat_surface_access import CHAT_SURFACE_ACCESS_KEY_SCOPE_ORDER
from shared.contracts.errors import AuthenticationError, ConflictError, NotFoundError
from shared.security.api_keys import hash_api_key, parse_project_api_key


class AuthenticateChatSurfaceAccessKeyUseCase:
    def __init__(self, repository: ChatSurfaceAccessKeyRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: AuthenticateChatSurfaceAccessKeyInput,
    ) -> ChatSurfaceAccessKeyState:
        parsed = parse_project_api_key(input_dto.credentials)
        if (
            parsed is None
            or parsed.kind != "chat_surface"
            or parsed.environment is not None
        ):
            raise AuthenticationError("Invalid ChatSurface Access Key")

        supplied_digest = hash_api_key(input_dto.credentials)
        candidates = await self._repository.find_authentication_candidates(
            chat_surface_id=input_dto.chat_surface_id,
            key_prefix=parsed.public_prefix,
            key_version=parsed.key_version,
        )
        matched = next(
            (
                candidate.key
                for candidate in candidates
                if compare_digest(candidate.key_hash, supplied_digest)
            ),
            None,
        )
        if matched is None:
            raise AuthenticationError("Invalid ChatSurface Access Key")

        now = datetime.now(UTC)
        expires_at = matched.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if (
            matched.status != "active"
            or matched.revoked_at is not None
            or (expires_at is not None and expires_at <= now)
        ):
            raise AuthenticationError("ChatSurface Access Key is inactive")
        return await self._repository.mark_used(matched.id, used_at=now)


class CreateChatSurfaceAccessKeyUseCase:
    def __init__(
        self,
        repository: ChatSurfaceAccessKeyRepository,
        issuer: ApiKeyIssuer,
    ) -> None:
        self._repository = repository
        self._issuer = issuer

    async def execute(
        self,
        input_dto: CreateChatSurfaceAccessKeyInput,
    ) -> ChatSurfaceAccessKeyMutationResult:
        issued = self._issuer.issue_chat_surface()
        key = await self._repository.create(
            PersistChatSurfaceAccessKeyInput(
                project_id=input_dto.project_id,
                credential_id=uuid4(),
                chat_surface_id=input_dto.chat_surface_id,
                name=input_dto.name,
                description=input_dto.description,
                key_prefix=issued.public_prefix,
                key_hash=issued.digest,
                key_version=issued.key_version,
                scopes=list(CHAT_SURFACE_ACCESS_KEY_SCOPE_ORDER),
                created_by_user_id=input_dto.actor_id,
            )
        )
        return ChatSurfaceAccessKeyMutationResult(
            key=key,
            secret=issued.value,
            display_prefix=issued.display_prefix,
        )


class ListChatSurfaceAccessKeysUseCase:
    def __init__(self, repository: ChatSurfaceAccessKeyRepository) -> None:
        self._repository = repository

    async def execute(self, input_dto: ListChatSurfaceAccessKeysInput):
        return await self._repository.list_by_surface(input_dto.chat_surface_id)


class RevokeChatSurfaceAccessKeyUseCase:
    def __init__(self, repository: ChatSurfaceAccessKeyRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: RevokeChatSurfaceAccessKeyInput,
    ) -> ChatSurfaceAccessKeyMutationResult:
        current = await self._repository.get_for_update(input_dto.api_key_id)
        if current is None or current.chat_surface_id != input_dto.chat_surface_id:
            raise NotFoundError("ChatSurface Access Key not found")
        key = await self._repository.revoke(
            current.id,
            revoked_at=datetime.now(UTC),
        )
        return ChatSurfaceAccessKeyMutationResult(key=key)


class RotateChatSurfaceAccessKeyUseCase:
    def __init__(
        self,
        repository: ChatSurfaceAccessKeyRepository,
        issuer: ApiKeyIssuer,
    ) -> None:
        self._repository = repository
        self._issuer = issuer

    async def execute(
        self,
        input_dto: RotateChatSurfaceAccessKeyInput,
    ) -> ChatSurfaceAccessKeyMutationResult:
        current = await self._repository.get_for_update(input_dto.api_key_id)
        if current is None or current.chat_surface_id != input_dto.chat_surface_id:
            raise NotFoundError("ChatSurface Access Key not found")
        if current.status != "active" or current.revoked_at is not None:
            raise ConflictError("Only active ChatSurface Access Keys can rotate")

        issued = self._issuer.issue_chat_surface()
        await self._repository.revoke(
            current.id,
            revoked_at=datetime.now(UTC),
        )
        replacement = await self._repository.create(
            PersistChatSurfaceAccessKeyInput(
                project_id=current.project_id,
                credential_id=current.credential_id,
                chat_surface_id=current.chat_surface_id,
                name=current.name,
                description=current.description,
                key_prefix=issued.public_prefix,
                key_hash=issued.digest,
                key_version=issued.key_version,
                scopes=list(current.scopes),
                expires_at=current.expires_at,
                created_by_user_id=input_dto.actor_id,
                rotated_from_id=current.id,
            )
        )
        return ChatSurfaceAccessKeyMutationResult(
            key=replacement,
            secret=issued.value,
            display_prefix=issued.display_prefix,
        )


__all__ = [
    "AuthenticateChatSurfaceAccessKeyUseCase",
    "CreateChatSurfaceAccessKeyUseCase",
    "ListChatSurfaceAccessKeysUseCase",
    "RevokeChatSurfaceAccessKeyUseCase",
    "RotateChatSurfaceAccessKeyUseCase",
]
