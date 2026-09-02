from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetChatSurfaceCredentialInput(BaseModel):
    credential_id: UUID


class ChatSurfaceCredentialState(BaseModel):
    id: UUID
    project_id: UUID
    chat_surface_id: UUID | None
    kind: str
    status: str
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
