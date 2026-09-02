from uuid import UUID

from modules.agent.entrypoint import build_agent_chat_surface_runtime
from modules.chat_surface.application.dtos.session_authorization import (
    ChatSurfaceCredentialAuthorizationState,
    TargetSessionAuthorizationInput,
)
from modules.chat_surface.application.interfaces.session_authorization import (
    ChatSurfaceCredentialReader,
    ChatSurfaceTargetSessionAuthorizer,
)
from modules.core.entrypoint import get_chat_surface_credential_composer
from modules.network.entrypoint import build_network_chat_surface_runtime
from shared.presentation.http.request import Request as InternalRequest


class CoreChatSurfaceCredentialReader(ChatSurfaceCredentialReader):
    async def get(
        self,
        credential_id: UUID,
    ) -> ChatSurfaceCredentialAuthorizationState | None:
        response = await get_chat_surface_credential_composer()(
            InternalRequest(path_params={"credential_id": str(credential_id)})
        )
        data = response.body["data"]
        return (
            ChatSurfaceCredentialAuthorizationState.model_validate(data)
            if data is not None
            else None
        )


class PublicTargetSessionAuthorizer(ChatSurfaceTargetSessionAuthorizer):
    async def is_authorized(
        self,
        input_dto: TargetSessionAuthorizationInput,
    ) -> bool:
        if input_dto.target_type == "agent":
            return await build_agent_chat_surface_runtime().validate_session(
                project_id=input_dto.project_id,
                agent_id=input_dto.target_id,
                session_id=input_dto.session_id,
                agent_release_id=input_dto.target_release_id,
                chat_surface_id=input_dto.chat_surface_id,
            )
        if input_dto.target_type == "network":
            return await build_network_chat_surface_runtime().validate_session(
                project_id=input_dto.project_id,
                network_id=input_dto.target_id,
                network_session_id=input_dto.session_id,
                network_version_id=input_dto.target_release_id,
                chat_surface_id=input_dto.chat_surface_id,
            )
        return False


__all__ = [
    "CoreChatSurfaceCredentialReader",
    "PublicTargetSessionAuthorizer",
]
