from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from modules.chat_surface.application.dtos.surface_mutation import CreateChatSurfaceInput
from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState
from modules.chat_surface.application.interfaces.surface_mutation_repository import (
    ChatSurfaceMutationRepository,
)
from modules.chat_surface.infra.database.models import ChatSurfaceModel
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from shared.contracts.errors import ConflictError, NotFoundError


class SQLAlchemyChatSurfaceMutationRepository(ChatSurfaceMutationRepository):
    def __init__(self, uow: ChatSurfaceUnitOfWork) -> None:
        self._uow = uow

    async def create(
        self,
        input_dto: CreateChatSurfaceInput,
        *,
        public_id: str,
        normalized_name: str,
        allowed_origins: list[str],
    ) -> ChatSurfaceState:
        model = ChatSurfaceModel(
            public_id=public_id,
            project_id=input_dto.project_id,
            name=" ".join(input_dto.name.split()),
            normalized_name=normalized_name,
            description=input_dto.description,
            target_type=input_dto.target_type,
            target_id=input_dto.target_id,
            target_release_id=input_dto.target_release_id,
            environment="production",
            status="draft",
            access_mode="backend_managed",
            allowed_origins=allowed_origins,
            appearance_config=input_dto.appearance_config,
            requests_per_minute=input_dto.requests_per_minute,
            max_concurrent_runs=input_dto.max_concurrent_runs,
            session_token_ttl_seconds=input_dto.session_token_ttl_seconds,
            token_epoch=1,
            created_by=input_dto.actor_id,
        )
        self._uow.session.add(model)
        try:
            await self._uow.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A ChatSurface with this name already exists in the Project"
            ) from exc
        return self._state(model)

    async def get_for_update(self, surface_id: UUID) -> ChatSurfaceState | None:
        model = await self._uow.session.get(
            ChatSurfaceModel,
            surface_id,
            with_for_update=True,
        )
        return self._state(model) if model is not None else None

    async def update(
        self,
        surface_id: UUID,
        changes: dict[str, Any],
    ) -> ChatSurfaceState:
        model = await self._uow.session.get(
            ChatSurfaceModel,
            surface_id,
            with_for_update=True,
        )
        if model is None:
            raise NotFoundError("ChatSurface not found")

        if "name" in changes:
            name = str(changes["name"])
            model.name = name
            model.normalized_name = name.casefold()
        for field in (
            "description",
            "allowed_origins",
            "appearance_config",
            "requests_per_minute",
            "max_concurrent_runs",
            "session_token_ttl_seconds",
        ):
            if field in changes:
                setattr(model, field, changes[field])

        try:
            await self._uow.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A ChatSurface with this name already exists in the Project"
            ) from exc
        return self._state(model)

    async def set_target_release(
        self,
        surface_id: UUID,
        target_release_id: UUID,
    ) -> ChatSurfaceState:
        model = await self._uow.session.get(
            ChatSurfaceModel,
            surface_id,
            with_for_update=True,
        )
        if model is None:
            raise NotFoundError("ChatSurface not found")
        model.target_release_id = target_release_id
        await self._uow.session.flush()
        return self._state(model)

    async def set_status(
        self,
        surface_id: UUID,
        *,
        status: str,
        token_epoch: int,
        activated_at: datetime | None,
        archived_at: datetime | None,
    ) -> ChatSurfaceState:
        model = await self._uow.session.get(
            ChatSurfaceModel,
            surface_id,
            with_for_update=True,
        )
        if model is None:
            raise NotFoundError("ChatSurface not found")
        model.status = status
        model.token_epoch = token_epoch
        model.activated_at = activated_at
        model.archived_at = archived_at
        await self._uow.session.flush()
        return self._state(model)

    @staticmethod
    def _state(model: ChatSurfaceModel) -> ChatSurfaceState:
        return ChatSurfaceState(
            id=model.id,
            public_id=model.public_id,
            project_id=model.project_id,
            name=model.name,
            description=model.description,
            target_type=model.target_type,
            target_id=model.target_id,
            target_release_id=model.target_release_id,
            environment=model.environment,
            status=model.status,
            access_mode=model.access_mode,
            allowed_origins=list(model.allowed_origins or []),
            appearance_config=dict(model.appearance_config or {}),
            requests_per_minute=model.requests_per_minute,
            max_concurrent_runs=model.max_concurrent_runs,
            session_token_ttl_seconds=model.session_token_ttl_seconds,
            token_epoch=model.token_epoch,
            activated_at=model.activated_at,
            archived_at=model.archived_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


__all__ = ["SQLAlchemyChatSurfaceMutationRepository"]
