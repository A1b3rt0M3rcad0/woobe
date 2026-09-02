from datetime import UTC, datetime
from uuid import UUID

from modules.chat_surface.application.dtos.message_request import (
    MarkMessageRequestInput,
    MessageRequestState,
)
from modules.chat_surface.application.interfaces.message_request_repository import (
    ChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.models import ChatSurfaceMessageRequestModel
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork


class SQLAlchemyChatSurfaceMessageRequestRepository(ChatSurfaceMessageRequestRepository):
    def __init__(self, uow: ChatSurfaceUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _state(model: ChatSurfaceMessageRequestModel) -> MessageRequestState:
        return MessageRequestState(
            id=model.id,
            session_binding_id=model.session_binding_id,
            idempotency_key=model.idempotency_key,
            status=str(model.status),
            target_run_id=model.target_run_id,
            error_code=model.error_code,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, request_id: UUID) -> MessageRequestState | None:
        model = await self._uow.session.get(ChatSurfaceMessageRequestModel, request_id)
        return self._state(model) if model is not None else None

    async def mark(
        self,
        input_dto: MarkMessageRequestInput,
    ) -> MessageRequestState | None:
        model = await self._uow.session.get(
            ChatSurfaceMessageRequestModel,
            input_dto.request_id,
            with_for_update=True,
        )
        if model is None:
            return None
        model.status = input_dto.status
        if input_dto.target_run_id is not None:
            model.target_run_id = input_dto.target_run_id
        model.error_code = input_dto.error_code
        if input_dto.status in {"completed", "failed", "cancelled"}:
            model.completed_at = datetime.now(UTC)
        await self._uow.session.flush()
        return self._state(model)
