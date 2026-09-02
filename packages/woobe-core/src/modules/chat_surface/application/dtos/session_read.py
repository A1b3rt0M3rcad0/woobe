from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatSurfaceSessionState(BaseModel):
    id: UUID
    chat_surface_id: UUID
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    external_reference: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ListChatSurfaceSessionsInput(BaseModel):
    surface_id: UUID
    limit: int = 50


class GetChatSurfaceActivityInput(BaseModel):
    surface_id: UUID


class ChatSurfaceActivityState(BaseModel):
    sessions: int
    active_sessions: int
