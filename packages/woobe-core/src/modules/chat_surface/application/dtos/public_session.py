from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ChatSurfaceSessionBindingState(BaseModel):
    id: UUID
    chat_surface_id: UUID
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    surface_credential_id: UUID
    idempotency_key: str
    external_reference: str | None = None
    metadata: dict[str, Any] | None = None
    status: str


class GetChatSurfaceSessionByIdempotencyInput(BaseModel):
    surface_id: UUID
    idempotency_key: str


class GetChatSurfaceSessionBindingInput(BaseModel):
    surface_id: UUID
    session_id: UUID


class CreateChatSurfaceSessionBindingInput(BaseModel):
    surface_id: UUID
    expected_project_id: UUID
    expected_target_type: str
    expected_target_id: UUID
    expected_target_release_id: UUID
    session_id: UUID
    surface_credential_id: UUID
    idempotency_key: str
    external_reference: str | None = None
    metadata: dict[str, Any] | None = None


class IssueChatSurfaceSessionTokenInput(BaseModel):
    surface_id: UUID
    session_id: UUID
    surface_credential_id: UUID
    origin: str


class ArchiveChatSurfaceSessionBindingInput(BaseModel):
    surface_id: UUID
    session_id: UUID


class ChatSurfaceSessionTokenResult(BaseModel):
    session_id: UUID
    target_release_id: UUID
    token: str
    expires_in: int
