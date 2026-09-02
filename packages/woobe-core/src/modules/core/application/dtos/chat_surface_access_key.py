from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatSurfaceAccessKeyState(BaseModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    chat_surface_id: UUID
    name: str
    description: str | None = None
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    rotated_from_id: UUID | None = None


class PersistChatSurfaceAccessKeyInput(BaseModel):
    project_id: UUID
    credential_id: UUID
    chat_surface_id: UUID
    name: str
    description: str | None = None
    key_prefix: str
    key_hash: bytes
    key_version: int
    scopes: list[str]
    expires_at: datetime | None = None
    created_by_user_id: UUID
    rotated_from_id: UUID | None = None


class CreateChatSurfaceAccessKeyInput(BaseModel):
    project_id: UUID
    chat_surface_id: UUID
    actor_id: UUID
    name: str
    description: str | None = None


class ListChatSurfaceAccessKeysInput(BaseModel):
    chat_surface_id: UUID


class RevokeChatSurfaceAccessKeyInput(BaseModel):
    chat_surface_id: UUID
    api_key_id: UUID


class RotateChatSurfaceAccessKeyInput(BaseModel):
    chat_surface_id: UUID
    api_key_id: UUID
    actor_id: UUID


class ChatSurfaceAccessKeyMutationResult(BaseModel):
    key: ChatSurfaceAccessKeyState
    secret: str | None = None
    display_prefix: str | None = None
