from modules.agent.application.dtos.chat_surface_session import (
    AgentChatSurfaceSessionState,
    CloseAgentChatSurfaceSessionInput,
    CreateAgentChatSurfaceSessionInput,
)
from modules.agent.application.interfaces.chat_surface_session_repository import (
    AgentChatSurfaceSessionRepository,
)
from modules.agent.infra.database.models import SessionModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.contracts.errors import NotFoundError


class SQLAlchemyAgentChatSurfaceSessionRepository(AgentChatSurfaceSessionRepository):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _state(model: SessionModel) -> AgentChatSurfaceSessionState:
        if model.opened_release_id is None or model.chat_surface_id is None:
            raise RuntimeError("ChatSurface Agent Session binding is incomplete")
        return AgentChatSurfaceSessionState(
            id=model.id,
            project_id=model.project_id,
            agent_id=model.agent_id,
            agent_release_id=model.opened_release_id,
            chat_surface_id=model.chat_surface_id,
            status=str(model.status),
        )

    async def create(
        self,
        input_dto: CreateAgentChatSurfaceSessionInput,
    ) -> AgentChatSurfaceSessionState:
        model = SessionModel(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            runtime_environment="production",
            opened_release_id=input_dto.agent_release_id,
            external_session_id=None,
            tenant_id=str(input_dto.chat_surface_id),
            user_id=None,
            status="active",
            mode="chat",
            data={
                "source": "chat_surface",
                "chat_surface_id": str(input_dto.chat_surface_id),
                "runtime_environment": "production",
                "loaded_release_id": str(input_dto.agent_release_id),
                "release_version": input_dto.release_version,
            },
            last_message_at=None,
            chat_surface_id=input_dto.chat_surface_id,
            origin="chat_surface",
        )
        self._uow.session.add(model)
        await self._uow.session.flush()
        return self._state(model)

    async def close(
        self,
        input_dto: CloseAgentChatSurfaceSessionInput,
    ) -> AgentChatSurfaceSessionState:
        model = await self._uow.session.get(
            SessionModel,
            input_dto.session_id,
            with_for_update=True,
        )
        if (
            model is None
            or model.project_id != input_dto.project_id
            or model.agent_id != input_dto.agent_id
            or model.opened_release_id != input_dto.agent_release_id
            or model.chat_surface_id != input_dto.chat_surface_id
            or model.runtime_environment != "production"
            or model.origin != "chat_surface"
        ):
            raise NotFoundError("ChatSurface Agent Session not found")
        if model.status != "closed":
            model.status = "closed"
            await self._uow.session.flush()
        return self._state(model)


__all__ = ["SQLAlchemyAgentChatSurfaceSessionRepository"]
