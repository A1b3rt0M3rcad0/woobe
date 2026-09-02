from uuid import UUID

from sqlalchemy import func, select

from modules.chat_surface.application.dtos.session_read import (
    ChatSurfaceActivityState,
    ChatSurfaceSessionState,
)
from modules.chat_surface.application.interfaces.session_read_repository import (
    ChatSurfaceSessionReadRepository,
)
from modules.chat_surface.infra.database.models import ChatSurfaceSessionBindingModel
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork


class SQLAlchemyChatSurfaceSessionReadRepository(ChatSurfaceSessionReadRepository):
    def __init__(self, uow: ChatSurfaceUnitOfWork) -> None:
        self._uow = uow

    async def list_by_surface(
        self,
        surface_id: UUID,
        *,
        limit: int,
    ) -> list[ChatSurfaceSessionState]:
        result = await self._uow.session.execute(
            select(ChatSurfaceSessionBindingModel)
            .where(ChatSurfaceSessionBindingModel.chat_surface_id == surface_id)
            .order_by(ChatSurfaceSessionBindingModel.updated_at.desc())
            .limit(limit)
        )
        return [self._state(item) for item in result.scalars().all()]

    async def activity(self, surface_id: UUID) -> ChatSurfaceActivityState:
        sessions = await self._uow.session.scalar(
            select(func.count(ChatSurfaceSessionBindingModel.id)).where(
                ChatSurfaceSessionBindingModel.chat_surface_id == surface_id
            )
        )
        active = await self._uow.session.scalar(
            select(func.count(ChatSurfaceSessionBindingModel.id)).where(
                ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                ChatSurfaceSessionBindingModel.status == "active",
            )
        )
        return ChatSurfaceActivityState(
            sessions=int(sessions or 0),
            active_sessions=int(active or 0),
        )

    @staticmethod
    def _state(model: ChatSurfaceSessionBindingModel) -> ChatSurfaceSessionState:
        return ChatSurfaceSessionState(
            id=model.id,
            chat_surface_id=model.chat_surface_id,
            project_id=model.project_id,
            target_type=model.target_type,
            target_id=model.target_id,
            target_release_id=model.target_release_id,
            session_id=model.session_id,
            external_reference=model.external_reference,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
