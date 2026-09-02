from abc import ABC, abstractmethod
from uuid import UUID

from modules.chat_surface.application.dtos.session_authorization import (
    ChatSessionClaims,
    ChatSurfaceCredentialAuthorizationState,
    ChatSurfaceSessionAuthorizationSnapshot,
    TargetSessionAuthorizationInput,
)


class ChatSessionTokenDecoder(ABC):
    @abstractmethod
    def decode(self, token: str) -> ChatSessionClaims: ...


class ChatSurfaceSessionAuthorizationRepository(ABC):
    @abstractmethod
    async def load(
        self,
        claims: ChatSessionClaims,
    ) -> ChatSurfaceSessionAuthorizationSnapshot: ...


class ChatSurfaceCredentialReader(ABC):
    @abstractmethod
    async def get(
        self,
        credential_id: UUID,
    ) -> ChatSurfaceCredentialAuthorizationState | None: ...


class ChatSurfaceTargetSessionAuthorizer(ABC):
    @abstractmethod
    async def is_authorized(
        self,
        input_dto: TargetSessionAuthorizationInput,
    ) -> bool: ...
