from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update

from modules.chat_surface.application.dtos.message_request import (
    MarkMessageRequestInput,
    MessageAdmissionSurfaceState,
    MessageRequestState,
)
from modules.chat_surface.application.interfaces.message_request_repository import (
    ChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.models import (
    ChatSurfaceMessageRequestModel,
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork


_ACTIVE_STATUSES = {"accepted", "streaming"}


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

    async def latest_for_binding(
        self,
        session_binding_id: UUID,
    ) -> MessageRequestState | None:
        active = await self._uow.session.scalar(
            select(ChatSurfaceMessageRequestModel)
            .where(
                ChatSurfaceMessageRequestModel.session_binding_id == session_binding_id,
                ChatSurfaceMessageRequestModel.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(
                ChatSurfaceMessageRequestModel.created_at.desc(),
                ChatSurfaceMessageRequestModel.id.desc(),
            )
            .limit(1)
        )
        if active is not None:
            return self._state(active)
        latest = await self._uow.session.scalar(
            select(ChatSurfaceMessageRequestModel)
            .where(ChatSurfaceMessageRequestModel.session_binding_id == session_binding_id)
            .order_by(
                ChatSurfaceMessageRequestModel.created_at.desc(),
                ChatSurfaceMessageRequestModel.id.desc(),
            )
            .limit(1)
        )
        return self._state(latest) if latest is not None else None

    async def lock_surface_for_admission(
        self,
        *,
        surface_id: UUID,
        session_binding_id: UUID,
    ) -> MessageAdmissionSurfaceState | None:
        surface = await self._uow.session.get(
            ChatSurfaceModel,
            surface_id,
            with_for_update=True,
        )
        if surface is None:
            return None
        binding = await self._uow.session.get(
            ChatSurfaceSessionBindingModel,
            session_binding_id,
        )
        if (
            binding is None
            or binding.chat_surface_id != surface.id
            or binding.status != "active"
        ):
            return None
        return MessageAdmissionSurfaceState(
            id=surface.id,
            status=str(surface.status),
            requests_per_minute=int(surface.requests_per_minute),
            max_concurrent_runs=int(surface.max_concurrent_runs),
        )

    async def expire_stale(
        self,
        *,
        session_binding_id: UUID,
        stale_before: datetime,
        completed_at: datetime,
    ) -> None:
        await self._uow.session.execute(
            update(ChatSurfaceMessageRequestModel)
            .where(
                ChatSurfaceMessageRequestModel.session_binding_id == session_binding_id,
                ChatSurfaceMessageRequestModel.status.in_(_ACTIVE_STATUSES),
                ChatSurfaceMessageRequestModel.updated_at < stale_before,
            )
            .values(
                status="failed",
                error_code="runtime_lease_expired",
                completed_at=completed_at,
            )
        )

    async def find_idempotent(
        self,
        *,
        session_binding_id: UUID,
        idempotency_key: str,
    ) -> MessageRequestState | None:
        model = await self._uow.session.scalar(
            select(ChatSurfaceMessageRequestModel).where(
                ChatSurfaceMessageRequestModel.session_binding_id == session_binding_id,
                ChatSurfaceMessageRequestModel.idempotency_key == idempotency_key,
            )
        )
        return self._state(model) if model is not None else None

    async def count_surface_requests(
        self,
        *,
        surface_id: UUID,
        since: datetime,
    ) -> int:
        value = await self._uow.session.scalar(
            select(func.count(ChatSurfaceMessageRequestModel.id))
            .join(
                ChatSurfaceSessionBindingModel,
                ChatSurfaceSessionBindingModel.id
                == ChatSurfaceMessageRequestModel.session_binding_id,
            )
            .where(
                ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                ChatSurfaceMessageRequestModel.created_at >= since,
            )
        )
        return int(value or 0)

    async def count_session_requests(
        self,
        *,
        session_binding_id: UUID,
        since: datetime,
    ) -> int:
        value = await self._uow.session.scalar(
            select(func.count(ChatSurfaceMessageRequestModel.id)).where(
                ChatSurfaceMessageRequestModel.session_binding_id == session_binding_id,
                ChatSurfaceMessageRequestModel.created_at >= since,
            )
        )
        return int(value or 0)

    async def count_surface_active(self, surface_id: UUID) -> int:
        value = await self._uow.session.scalar(
            select(func.count(ChatSurfaceMessageRequestModel.id))
            .join(
                ChatSurfaceSessionBindingModel,
                ChatSurfaceSessionBindingModel.id
                == ChatSurfaceMessageRequestModel.session_binding_id,
            )
            .where(
                ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                ChatSurfaceMessageRequestModel.status.in_(_ACTIVE_STATUSES),
            )
        )
        return int(value or 0)

    async def create(
        self,
        *,
        session_binding_id: UUID,
        idempotency_key: str,
    ) -> MessageRequestState:
        model = ChatSurfaceMessageRequestModel(
            session_binding_id=session_binding_id,
            idempotency_key=idempotency_key,
            status="accepted",
        )
        self._uow.session.add(model)
        await self._uow.session.flush()
        return self._state(model)

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
