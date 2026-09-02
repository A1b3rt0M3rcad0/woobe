from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from modules.core.application.dtos.chat_surface_access_key import (
    ChatSurfaceAccessKeyState,
    PersistChatSurfaceAccessKeyInput,
)
from modules.core.application.interfaces.chat_surface_access_key_repository import (
    ChatSurfaceAccessKeyRepository,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.core.infra.database.unit_of_work import CoreUnitOfWork


class SQLAlchemyChatSurfaceAccessKeyRepository(ChatSurfaceAccessKeyRepository):
    def __init__(self, uow: CoreUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _state(model: ApiKeyModel) -> ChatSurfaceAccessKeyState:
        if model.chat_surface_id is None:
            raise RuntimeError("ChatSurface Access Key is missing chat_surface_id")
        return ChatSurfaceAccessKeyState(
            id=model.id,
            credential_id=model.credential_id,
            project_id=model.project_id,
            chat_surface_id=model.chat_surface_id,
            name=model.name,
            description=model.description,
            key_prefix=model.key_prefix,
            scopes=list(model.scopes or []),
            status=model.status,
            last_used_at=model.last_used_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
            rotated_from_id=model.rotated_from_id,
        )

    async def create(
        self,
        input_dto: PersistChatSurfaceAccessKeyInput,
    ) -> ChatSurfaceAccessKeyState:
        model = ApiKeyModel(
            project_id=input_dto.project_id,
            credential_id=input_dto.credential_id,
            name=input_dto.name,
            description=input_dto.description,
            key_prefix=input_dto.key_prefix,
            key_hash=input_dto.key_hash,
            key_version=input_dto.key_version,
            scopes=list(input_dto.scopes),
            kind="chat_surface",
            agent_id=None,
            target_type=None,
            target_id=None,
            chat_surface_id=input_dto.chat_surface_id,
            environment=None,
            interfaces=[],
            status="active",
            expires_at=input_dto.expires_at,
            created_by_user_id=input_dto.created_by_user_id,
            rotated_from_id=input_dto.rotated_from_id,
        )
        self._uow.session.add(model)
        await self._uow.session.flush()
        await self._uow.session.refresh(model)
        return self._state(model)

    async def list_by_surface(
        self,
        chat_surface_id: UUID,
    ) -> list[ChatSurfaceAccessKeyState]:
        result = await self._uow.session.execute(
            select(ApiKeyModel)
            .where(
                ApiKeyModel.chat_surface_id == chat_surface_id,
                ApiKeyModel.kind == "chat_surface",
            )
            .order_by(ApiKeyModel.created_at.desc())
        )
        return [self._state(model) for model in result.scalars().all()]

    async def get_for_update(
        self,
        api_key_id: UUID,
    ) -> ChatSurfaceAccessKeyState | None:
        model = await self._uow.session.get(
            ApiKeyModel,
            api_key_id,
            with_for_update=True,
        )
        if model is None or model.kind != "chat_surface":
            return None
        return self._state(model)

    async def revoke(
        self,
        api_key_id: UUID,
        *,
        revoked_at: datetime,
    ) -> ChatSurfaceAccessKeyState:
        model = await self._uow.session.get(
            ApiKeyModel,
            api_key_id,
            with_for_update=True,
        )
        if model is None or model.kind != "chat_surface":
            raise LookupError("ChatSurface Access Key does not exist")
        model.status = "revoked"
        model.revoked_at = revoked_at
        await self._uow.session.flush()
        await self._uow.session.refresh(model)
        return self._state(model)
