from datetime import UTC, datetime
from uuid import uuid4

from modules.core.application.dtos.chat_surface_access_key import (
    ChatSurfaceAccessKeyMutationResult,
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
from shared.contracts.errors import ConflictError, NotFoundError


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
    "CreateChatSurfaceAccessKeyUseCase",
    "ListChatSurfaceAccessKeysUseCase",
    "RevokeChatSurfaceAccessKeyUseCase",
    "RotateChatSurfaceAccessKeyUseCase",
]
