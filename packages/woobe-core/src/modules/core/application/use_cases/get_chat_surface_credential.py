from modules.core.application.dtos.chat_surface_credential import (
    ChatSurfaceCredentialState,
    GetChatSurfaceCredentialInput,
)
from modules.core.application.interfaces.chat_surface_credential_repository import (
    ChatSurfaceCredentialRepository,
)


class GetChatSurfaceCredentialUseCase:
    def __init__(self, repository: ChatSurfaceCredentialRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: GetChatSurfaceCredentialInput,
    ) -> ChatSurfaceCredentialState | None:
        return await self._repository.get(input_dto.credential_id)
