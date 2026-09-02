from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatSessionClaims(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: UUID
    chat_surface_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    origin: str
    surface_credential_id: UUID
    token_epoch: int
    permissions: frozenset[str]
    issued_at: datetime
    expires_at: datetime
    jti: UUID


class AuthorizeChatSurfaceSessionInput(BaseModel):
    token: str
    expected_session_id: UUID
    host_origin: str
    permission: str
    allow_insecure_origins: bool = False


class ChatSurfaceAuthorizationState(BaseModel):
    id: UUID
    public_id: str
    project_id: UUID
    name: str
    target_type: str
    target_id: UUID
    status: str
    allowed_origins: list[str]
    appearance_config: dict[str, Any]
    token_epoch: int


class ChatSurfaceSessionBindingAuthorizationState(BaseModel):
    id: UUID
    chat_surface_id: UUID
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    surface_credential_id: UUID
    status: str
    metadata: dict[str, Any] | None = None


class ChatSurfaceCredentialAuthorizationState(BaseModel):
    id: UUID
    project_id: UUID
    chat_surface_id: UUID | None
    kind: str
    status: str
    revoked_at: datetime | None = None
    expires_at: datetime | None = None


class ChatSurfaceSessionAuthorizationSnapshot(BaseModel):
    surface: ChatSurfaceAuthorizationState | None = None
    binding: ChatSurfaceSessionBindingAuthorizationState | None = None
    credential: ChatSurfaceCredentialAuthorizationState | None = None


class TargetSessionAuthorizationInput(BaseModel):
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    chat_surface_id: UUID


class AuthorizedChatSession(BaseModel):
    surface: ChatSurfaceAuthorizationState
    binding: ChatSurfaceSessionBindingAuthorizationState
    claims: ChatSessionClaims
