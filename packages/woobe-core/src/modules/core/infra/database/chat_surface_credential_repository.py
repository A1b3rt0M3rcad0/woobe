from uuid import UUID

from modules.core.application.dtos.chat_surface_credential import (
    ChatSurfaceCredentialState,
)
from modules.core.application.interfaces.chat_surface_credential_repository import (
    ChatSurfaceCredentialRepository,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.core.infra.database.unit_of_work import CoreUnitOfWork


class SQLAlchemyChatSurfaceCredentialRepository(ChatSurfaceCredentialRepository):
    def __init__(self, uow: CoreUnitOfWork) -> None:
        self._uow = uow

    async def get(
        self,
        credential_id: UUID,
    ) -> ChatSurfaceCredentialState | None:
        model = await self._uow.session.get(ApiKeyModel, credential_id)
        if model is None:
            return None
        return ChatSurfaceCredentialState(
            id=model.id,
            project_id=model.project_id,
            chat_surface_id=model.chat_surface_id,
            kind=str(model.kind),
            status=str(model.status),
            revoked_at=model.revoked_at,
            expires_at=model.expires_at,
        )
