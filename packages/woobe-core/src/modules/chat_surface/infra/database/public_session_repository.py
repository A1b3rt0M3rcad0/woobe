from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.chat_surface.application.dtos.public_session import (
    ChatSurfaceSessionBindingState,
    CreateChatSurfaceSessionBindingInput,
)
from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState
from modules.chat_surface.application.interfaces.public_session_repository import (
    ChatSurfacePublicSessionRepository,
)
from modules.chat_surface.infra.database.models import (
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork


class SQLAlchemyChatSurfacePublicSessionRepository(ChatSurfacePublicSessionRepository):
    def __init__(self, uow: ChatSurfaceUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _surface_state(model: ChatSurfaceModel) -> ChatSurfaceState:
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

    @staticmethod
    def _binding_state(
        model: ChatSurfaceSessionBindingModel,
    ) -> ChatSurfaceSessionBindingState:
        return ChatSurfaceSessionBindingState(
            id=model.id,
            chat_surface_id=model.chat_surface_id,
            project_id=model.project_id,
            target_type=str(model.target_type),
            target_id=model.target_id,
            target_release_id=model.target_release_id,
            session_id=model.session_id,
            surface_credential_id=model.surface_credential_id,
            idempotency_key=model.idempotency_key,
            external_reference=model.external_reference,
            metadata=dict(model.metadata_ or {}) or None,
            status=str(model.status),
        )

    async def get_surface(
        self,
        surface_id: UUID,
        *,
        for_update: bool = False,
    ) -> ChatSurfaceState | None:
        model = await self._uow.session.get(
            ChatSurfaceModel,
            surface_id,
            with_for_update=for_update,
        )
        return self._surface_state(model) if model is not None else None

    async def get_by_idempotency(
        self,
        surface_id: UUID,
        idempotency_key: str,
    ) -> ChatSurfaceSessionBindingState | None:
        model = await self._uow.session.scalar(
            select(ChatSurfaceSessionBindingModel).where(
                ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                ChatSurfaceSessionBindingModel.idempotency_key == idempotency_key,
            )
        )
        return self._binding_state(model) if model is not None else None

    async def get_binding(
        self,
        surface_id: UUID,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> ChatSurfaceSessionBindingState | None:
        statement = select(ChatSurfaceSessionBindingModel).where(
            ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
            ChatSurfaceSessionBindingModel.session_id == session_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self._uow.session.scalar(statement)
        return self._binding_state(model) if model is not None else None

    async def create_binding(
        self,
        input_dto: CreateChatSurfaceSessionBindingInput,
        *,
        idempotency_key: str,
    ) -> ChatSurfaceSessionBindingState:
        model = ChatSurfaceSessionBindingModel(
            chat_surface_id=input_dto.surface_id,
            project_id=input_dto.expected_project_id,
            target_type=input_dto.expected_target_type,
            target_id=input_dto.expected_target_id,
            target_release_id=input_dto.expected_target_release_id,
            session_id=input_dto.session_id,
            surface_credential_id=input_dto.surface_credential_id,
            idempotency_key=idempotency_key,
            external_reference=input_dto.external_reference,
            metadata_=input_dto.metadata,
            status="active",
        )
        try:
            async with self._uow.session.begin_nested():
                self._uow.session.add(model)
                await self._uow.session.flush()
        except IntegrityError:
            existing = await self.get_by_idempotency(
                input_dto.surface_id,
                idempotency_key,
            )
            if existing is not None:
                return existing
            raise
        return self._binding_state(model)

    async def archive_binding(
        self,
        surface_id: UUID,
        session_id: UUID,
    ) -> ChatSurfaceSessionBindingState:
        statement = (
            select(ChatSurfaceSessionBindingModel)
            .where(
                ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                ChatSurfaceSessionBindingModel.session_id == session_id,
            )
            .with_for_update()
        )
        model = await self._uow.session.scalar(statement)
        if model is None:
            raise LookupError("ChatSurface Session does not exist")
        model.status = "archived"
        await self._uow.session.flush()
        return self._binding_state(model)


__all__ = ["SQLAlchemyChatSurfacePublicSessionRepository"]
