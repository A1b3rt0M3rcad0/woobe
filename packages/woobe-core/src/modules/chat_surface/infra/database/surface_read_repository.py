from uuid import UUID

from sqlalchemy import select

from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState
from modules.chat_surface.application.interfaces.surface_read_repository import (
    ChatSurfaceReadRepository,
)
from modules.chat_surface.infra.database.models import ChatSurfaceModel
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork


class SQLAlchemyChatSurfaceReadRepository(ChatSurfaceReadRepository):
    def __init__(self, uow: ChatSurfaceUnitOfWork) -> None:
        self._uow = uow

    async def list_by_project(self, project_id: UUID) -> list[ChatSurfaceState]:
        result = await self._uow.session.execute(
            select(ChatSurfaceModel)
            .where(ChatSurfaceModel.project_id == project_id)
            .order_by(ChatSurfaceModel.created_at.desc())
        )
        return [self._state(item) for item in result.scalars().all()]

    async def get_by_id(self, surface_id: UUID) -> ChatSurfaceState | None:
        model = await self._uow.session.get(ChatSurfaceModel, surface_id)
        return self._state(model) if model is not None else None

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
