from sqlalchemy import select

from modules.chat_surface.application.dtos.session_authorization import (
    ChatSessionClaims,
    ChatSurfaceAuthorizationState,
    ChatSurfaceSessionAuthorizationSnapshot,
    ChatSurfaceSessionBindingAuthorizationState,
)
from modules.chat_surface.application.interfaces.session_authorization import (
    ChatSurfaceSessionAuthorizationRepository,
)
from modules.chat_surface.infra.database.models import (
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork


class SQLAlchemyChatSurfaceSessionAuthorizationRepository(
    ChatSurfaceSessionAuthorizationRepository
):
    def __init__(self, uow: ChatSurfaceUnitOfWork) -> None:
        self._uow = uow

    async def load(
        self,
        claims: ChatSessionClaims,
    ) -> ChatSurfaceSessionAuthorizationSnapshot:
        surface_model = await self._uow.session.get(
            ChatSurfaceModel,
            claims.chat_surface_id,
        )
        surface = (
            ChatSurfaceAuthorizationState(
                id=surface_model.id,
                public_id=surface_model.public_id,
                project_id=surface_model.project_id,
                name=surface_model.name,
                target_type=surface_model.target_type,
                target_id=surface_model.target_id,
                status=surface_model.status,
                allowed_origins=list(surface_model.allowed_origins or []),
                appearance_config=dict(surface_model.appearance_config or {}),
                token_epoch=surface_model.token_epoch,
            )
            if surface_model is not None
            else None
        )

        binding_model = await self._uow.session.scalar(
            select(ChatSurfaceSessionBindingModel).where(
                ChatSurfaceSessionBindingModel.chat_surface_id
                == claims.chat_surface_id,
                ChatSurfaceSessionBindingModel.session_id == claims.session_id,
            )
        )
        binding = (
            ChatSurfaceSessionBindingAuthorizationState(
                id=binding_model.id,
                chat_surface_id=binding_model.chat_surface_id,
                project_id=binding_model.project_id,
                target_type=binding_model.target_type,
                target_id=binding_model.target_id,
                target_release_id=binding_model.target_release_id,
                session_id=binding_model.session_id,
                surface_credential_id=binding_model.surface_credential_id,
                status=binding_model.status,
                metadata=dict(binding_model.metadata_ or {}),
            )
            if binding_model is not None
            else None
        )
        return ChatSurfaceSessionAuthorizationSnapshot(
            surface=surface,
            binding=binding,
        )
