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


class ChatSessionTokenIssuer(ABC):
    @abstractmethod
    def issue(
        self,
        *,
        project_id: UUID,
        chat_surface_id: UUID,
        target_type: str,
        target_id: UUID,
        target_release_id: UUID,
        session_id: UUID,
        origin: str,
        surface_credential_id: UUID,
        token_epoch: int,
        ttl_seconds: int | None = None,
    ) -> str: ...


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
