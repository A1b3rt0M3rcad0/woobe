from datetime import UTC, datetime
import secrets
from typing import Any

from modules.chat_surface.application.dtos.surface_mutation import (
    ActivateChatSurfaceInput,
    ChangeChatSurfaceStatusInput,
    CreateChatSurfaceInput,
    RefreshChatSurfaceReleaseInput,
    UpdateChatSurfaceInput,
)
from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState
from modules.chat_surface.application.interfaces.surface_mutation_repository import (
    ChatSurfaceMutationRepository,
)
from modules.chat_surface.domain.origin import normalize_origin
from shared.contracts.errors import ConflictError, NotFoundError


class CreateChatSurfaceUseCase:
    def __init__(
        self,
        repository: ChatSurfaceMutationRepository,
        *,
        allow_insecure_origins: bool,
    ) -> None:
        self._repository = repository
        self._allow_insecure_origins = allow_insecure_origins

    async def execute(self, input_dto: CreateChatSurfaceInput) -> ChatSurfaceState:
        name = " ".join(input_dto.name.split())
        origins = [
            normalize_origin(
                origin,
                allow_insecure=self._allow_insecure_origins,
            )
            for origin in input_dto.allowed_origins
        ]
        return await self._repository.create(
            input_dto,
            public_id=f"csf_{secrets.token_urlsafe(12).rstrip('=')}",
            normalized_name=name.casefold(),
            allowed_origins=list(dict.fromkeys(origins)),
        )


class UpdateChatSurfaceUseCase:
    def __init__(
        self,
        repository: ChatSurfaceMutationRepository,
        *,
        allow_insecure_origins: bool,
    ) -> None:
        self._repository = repository
        self._allow_insecure_origins = allow_insecure_origins

    async def execute(self, input_dto: UpdateChatSurfaceInput) -> ChatSurfaceState:
        current = await self._repository.get_for_update(input_dto.surface_id)
        if current is None:
            raise NotFoundError("ChatSurface not found")
        if current.status == "archived":
            raise ConflictError("Archived ChatSurface cannot be changed")

        fields = input_dto.model_fields_set - {"surface_id"}
        changes: dict[str, Any] = {}

        if "name" in fields:
            changes["name"] = " ".join(str(input_dto.name).split())
        if "description" in fields:
            changes["description"] = input_dto.description
        if "allowed_origins" in fields:
            normalized = [
                normalize_origin(
                    origin,
                    allow_insecure=self._allow_insecure_origins,
                )
                for origin in (input_dto.allowed_origins or [])
            ]
            changes["allowed_origins"] = list(dict.fromkeys(normalized))
        if "appearance_config" in fields:
            changes["appearance_config"] = input_dto.appearance_config or {}
        for field in (
            "requests_per_minute",
            "max_concurrent_runs",
            "session_token_ttl_seconds",
        ):
            if field in fields:
                changes[field] = getattr(input_dto, field)

        return await self._repository.update(input_dto.surface_id, changes)


class RefreshChatSurfaceReleaseUseCase:
    def __init__(self, repository: ChatSurfaceMutationRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: RefreshChatSurfaceReleaseInput,
    ) -> ChatSurfaceState:
        current = await self._repository.get_for_update(input_dto.surface_id)
        if current is None:
            raise NotFoundError("ChatSurface not found")
        if current.status == "archived":
            raise ConflictError("Archived ChatSurface cannot change Release")
        return await self._repository.set_target_release(
            input_dto.surface_id,
            input_dto.target_release_id,
        )


class ActivateChatSurfaceUseCase:
    def __init__(self, repository: ChatSurfaceMutationRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ActivateChatSurfaceInput,
    ) -> ChatSurfaceState:
        current = await self._repository.get_for_update(input_dto.surface_id)
        if current is None:
            raise NotFoundError("ChatSurface not found")
        if current.status == "archived":
            raise ConflictError("Archived ChatSurface cannot be reactivated")
        if not current.allowed_origins:
            raise ConflictError("Active ChatSurface requires at least one allowed origin")
        if current.target_release_id != input_dto.expected_target_release_id:
            raise ConflictError("ChatSurface Release changed during activation; retry")
        return await self._repository.set_status(
            input_dto.surface_id,
            status="active",
            token_epoch=current.token_epoch,
            activated_at=datetime.now(UTC),
            archived_at=current.archived_at,
        )


class DisableChatSurfaceUseCase:
    def __init__(self, repository: ChatSurfaceMutationRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ChangeChatSurfaceStatusInput,
    ) -> ChatSurfaceState:
        current = await self._repository.get_for_update(input_dto.surface_id)
        if current is None:
            raise NotFoundError("ChatSurface not found")
        if current.status == "archived":
            raise ConflictError("Archived ChatSurface cannot be reactivated")
        return await self._repository.set_status(
            input_dto.surface_id,
            status="disabled",
            token_epoch=current.token_epoch + 1,
            activated_at=current.activated_at,
            archived_at=current.archived_at,
        )


class ArchiveChatSurfaceUseCase:
    def __init__(self, repository: ChatSurfaceMutationRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ChangeChatSurfaceStatusInput,
    ) -> ChatSurfaceState:
        current = await self._repository.get_for_update(input_dto.surface_id)
        if current is None:
            raise NotFoundError("ChatSurface not found")
        if current.status == "archived":
            raise ConflictError("Archived ChatSurface cannot be reactivated")
        return await self._repository.set_status(
            input_dto.surface_id,
            status="archived",
            token_epoch=current.token_epoch + 1,
            activated_at=current.activated_at,
            archived_at=datetime.now(UTC),
        )


__all__ = [
    "ActivateChatSurfaceUseCase",
    "ArchiveChatSurfaceUseCase",
    "CreateChatSurfaceUseCase",
    "DisableChatSurfaceUseCase",
    "RefreshChatSurfaceReleaseUseCase",
    "UpdateChatSurfaceUseCase",
]
