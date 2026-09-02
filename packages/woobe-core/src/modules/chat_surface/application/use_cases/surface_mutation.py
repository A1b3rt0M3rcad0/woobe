from datetime import UTC, datetime
from typing import Any

from modules.chat_surface.application.dtos.surface_mutation import (
    ChangeChatSurfaceStatusInput,
    UpdateChatSurfaceInput,
)
from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState
from modules.chat_surface.application.interfaces.surface_mutation_repository import (
    ChatSurfaceMutationRepository,
)
from modules.chat_surface.domain.origin import normalize_origin
from shared.contracts.errors import ConflictError, NotFoundError


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
            archived_at=datetime.now(UTC),
        )


__all__ = [
    "ArchiveChatSurfaceUseCase",
    "DisableChatSurfaceUseCase",
    "UpdateChatSurfaceUseCase",
]
