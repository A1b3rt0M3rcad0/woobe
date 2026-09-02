from modules.network.application.dtos.chat_surface_session import (
    CloseNetworkChatSurfaceSessionInput,
    CreateNetworkChatSurfaceSessionInput,
    NetworkChatSurfaceSessionState,
)
from modules.network.application.interfaces.chat_surface_session_repository import (
    NetworkChatSurfaceSessionRepository,
)
from modules.network.infra.database.models import NetworkSessionModel
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from shared.contracts.errors import NotFoundError


class SQLAlchemyNetworkChatSurfaceSessionRepository(
    NetworkChatSurfaceSessionRepository
):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _state(model: NetworkSessionModel) -> NetworkChatSurfaceSessionState:
        if model.network_version_id is None or model.chat_surface_id is None:
            raise RuntimeError("ChatSurface Network Session binding is incomplete")
        return NetworkChatSurfaceSessionState(
            id=model.id,
            project_id=model.project_id,
            network_id=model.network_id,
            network_version_id=model.network_version_id,
            chat_surface_id=model.chat_surface_id,
            status=str(model.status),
        )

    async def create(
        self,
        input_dto: CreateNetworkChatSurfaceSessionInput,
    ) -> NetworkChatSurfaceSessionState:
        model = NetworkSessionModel(
            network_id=input_dto.network_id,
            network_version_id=input_dto.network_version_id,
            project_id=input_dto.project_id,
            environment="production",
            title="ChatSurface session",
            tenant_id=str(input_dto.chat_surface_id),
            user_id=None,
            external_session_id=None,
            status="active",
            chat_surface_id=input_dto.chat_surface_id,
            origin="chat_surface",
        )
        self._uow.session.add(model)
        await self._uow.session.flush()
        return self._state(model)

    async def close(
        self,
        input_dto: CloseNetworkChatSurfaceSessionInput,
    ) -> NetworkChatSurfaceSessionState:
        model = await self._uow.session.get(
            NetworkSessionModel,
            input_dto.session_id,
            with_for_update=True,
        )
        if (
            model is None
            or model.project_id != input_dto.project_id
            or model.network_id != input_dto.network_id
            or model.network_version_id != input_dto.network_version_id
            or model.chat_surface_id != input_dto.chat_surface_id
            or model.environment != "production"
            or model.origin != "chat_surface"
        ):
            raise NotFoundError("ChatSurface Network Session not found")
        if model.status != "archived":
            model.status = "archived"
            await self._uow.session.flush()
        return self._state(model)


__all__ = ["SQLAlchemyNetworkChatSurfaceSessionRepository"]
